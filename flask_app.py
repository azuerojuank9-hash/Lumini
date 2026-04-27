import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, abort, jsonify
import sqlite3, hashlib, os, time, secrets, logging
from datetime import timedelta
from io import BytesIO
app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400  # Cache 24 horas
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(hours=4)

# ── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('lumini.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
DB_FOLDER   = os.path.join(os.path.dirname(__file__), 'colegios_db')
MASTER_DB   = os.path.join(os.path.dirname(__file__), 'master.db')
LOGO_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'logos')
os.makedirs(DB_FOLDER, exist_ok=True)
os.makedirs(LOGO_FOLDER, exist_ok=True)

# ── CREDENCIALES DESDE .env ───────────────────────────────────────────────────
ADMIN_PASSWORD   = os.environ.get('ADMIN_PASSWORD')
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
EMAIL_ORIGEN     = os.environ.get('EMAIL_ORIGEN', 'lumini.appag@gmail.com')

if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD no está definido en .env")
if not SENDGRID_API_KEY:
    logger.warning("SENDGRID_API_KEY no definido — el envío de correos estará deshabilitado.")

app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def extension_permitida(filename):
    return '.' in filename and filename.rsplit('.', 1)[-1].lower() in EXTENSIONES_PERMITIDAS

JORNADAS = ['Mañana', 'Tarde', 'Nocturna']

MATERIAS = [
    'Artes', 'Matemáticas', 'Cipol y Econ', 'Física', 'Química',
    'Español', 'Inglés', 'Biología', 'Sociales',
    'Tecnología e Informática', 'Filosofía', 'Educación Física'
]

PREGUNTAS_SECRETAS = [
    '¿Cuál es el nombre de tu mascota?',
    '¿En qué ciudad naciste?',
    '¿Cuál es el nombre de tu colegio favorito?',
    '¿Cuál es tu comida favorita?',
    '¿Cuál es el nombre de tu mejor amigo(a)?',
    '¿Cuál es tu color favorito?',
    '¿Cuál es el nombre de tu madre?',
    '¿Cuál es tu deporte favorito?',
]

# ── CSRF ──────────────────────────────────────────────────────────────────────
def generar_csrf():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

def validar_csrf():
    token = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
    return bool(token and token == session.get('_csrf_token'))

app.jinja_env.globals['csrf_token'] = generar_csrf

# ── FUERZA BRUTA ──────────────────────────────────────────────────────────────
login_intentos = {}

def ip_bloqueada(ip, prefijo=''):
    clave = f'{prefijo}_{ip}'
    d = login_intentos.get(clave)
    if not d: return False
    if d['bloqueado_hasta'] and time.time() < d['bloqueado_hasta']:
        return int(d['bloqueado_hasta'] - time.time())
    return False

def registrar_fallo(ip, prefijo=''):
    clave = f'{prefijo}_{ip}'
    d = login_intentos.setdefault(clave, {'intentos': 0, 'bloqueado_hasta': None})
    d['intentos'] += 1
    if d['intentos'] >= 5:
        d['bloqueado_hasta'] = time.time() + 300
        logger.warning(f"IP bloqueada por fuerza bruta: {ip} (ctx={prefijo})")
    return d['intentos']

def limpiar_intentos(ip, prefijo=''):
    login_intentos.pop(f'{prefijo}_{ip}', None)

# ── HASH ──────────────────────────────────────────────────────────────────────
def hash_pw(pw, sal=None):
    if sal is None: sal = secrets.token_hex(16)
    return f"{sal}${hashlib.sha256((sal + pw).encode()).hexdigest()}"

def verificar_pw(plano, guardada):
    if not guardada: return False
    if '$' in guardada:
        sal, _ = guardada.split('$', 1)
        return hash_pw(plano, sal) == guardada
    return hashlib.sha256(plano.encode()).hexdigest() == guardada

def necesita_rehash(guardada):
    return '$' not in guardada

# ── MASTER DB ─────────────────────────────────────────────────────────────────
def conectar_master():
    c = sqlite3.connect(MASTER_DB)
    c.row_factory = sqlite3.Row
    return c

def init_master_db():
    conn = conectar_master()
    conn.execute('''CREATE TABLE IF NOT EXISTS colegios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL, nombre TEXT NOT NULL,
        logo TEXT DEFAULT '', activo INTEGER DEFAULT 1,
        creado TEXT DEFAULT (date('now')),
        vencimiento TEXT DEFAULT NULL,
        num_periodos INTEGER DEFAULT 4,
        codigo_registro TEXT DEFAULT ''
    )''')
    # Migraciones de columnas nuevas
    for col in [
        'logo TEXT DEFAULT ""',
        'vencimiento TEXT DEFAULT NULL',
        'num_periodos INTEGER DEFAULT 4',
        'codigo_registro TEXT DEFAULT ""',
    ]:
        try: conn.execute(f'ALTER TABLE colegios ADD COLUMN {col}')
        except: pass
    conn.commit()
    conn.close()

def get_colegio(slug):
    c = conectar_master()
    r = c.execute('SELECT * FROM colegios WHERE slug=?', (slug,)).fetchone()
    c.close()
    return r

def colegio_activo(slug):
    c = get_colegio(slug)
    return c and c['activo'] == 1

def get_codigo_registro(slug):
    """Devuelve el código de invitación específico del colegio."""
    c = get_colegio(slug)
    if c and c['codigo_registro']:
        return c['codigo_registro']
    return ''  # sin código = registro libre (solo si está vacío)

# ── DB POR COLEGIO ────────────────────────────────────────────────────────────
def db_path(slug): return os.path.join(DB_FOLDER, f'{slug}.db')

def conectar(slug):
    c = sqlite3.connect(db_path(slug))
    c.row_factory = sqlite3.Row
    return c

def migrar_db(slug):
    conn = conectar(slug)
    try:
        cols_prof = [r[1] for r in conn.execute('PRAGMA table_info(profesores)').fetchall()]
        if 'materia' in cols_prof:
            conn.execute('''CREATE TABLE IF NOT EXISTS profesores_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL, usuario TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL, activo INTEGER DEFAULT 1,
                email TEXT DEFAULT '', telefono TEXT DEFAULT '',
                pregunta_secreta TEXT DEFAULT '', respuesta_secreta TEXT DEFAULT '')''')
            conn.execute('''INSERT OR IGNORE INTO profesores_new
                (id,nombre,usuario,password,activo,email,telefono,pregunta_secreta,respuesta_secreta)
                SELECT id,nombre,usuario,password,activo,
                       COALESCE(email,''), COALESCE(telefono,''),
                       COALESCE(pregunta_secreta,''), COALESCE(respuesta_secreta,'')
                FROM profesores''')
            conn.execute('DROP TABLE profesores')
            conn.execute('ALTER TABLE profesores_new RENAME TO profesores')
            conn.commit()

        cols_dir = [r[1] for r in conn.execute('PRAGMA table_info(directoras)').fetchall()]
        for col, defval in [
            ('jornada',           'TEXT NOT NULL DEFAULT "Mañana"'),
            ('activo',            'INTEGER DEFAULT 1'),
            ('email',             'TEXT DEFAULT ""'),
            ('pregunta_secreta',  'TEXT DEFAULT ""'),
            ('respuesta_secreta', 'TEXT DEFAULT ""'),
        ]:
            if col not in cols_dir:
                conn.execute(f'ALTER TABLE directoras ADD COLUMN {col} {defval}')
                conn.commit()

        cols_alum = [r[1] for r in conn.execute('PRAGMA table_info(alumnos)').fetchall()]
        if 'jornada' not in cols_alum:
            conn.execute('ALTER TABLE alumnos ADD COLUMN jornada TEXT NOT NULL DEFAULT "Mañana"')
            conn.commit()
        if 'email_acudiente' not in cols_alum:
            conn.execute('ALTER TABLE alumnos ADD COLUMN email_acudiente TEXT DEFAULT ""')
            conn.commit()

        cols_act = [r[1] for r in conn.execute('PRAGMA table_info(actividades)').fetchall()]
        if 'periodo' not in cols_act:
            conn.execute('ALTER TABLE actividades ADD COLUMN periodo INTEGER DEFAULT 1')
            conn.commit()
        if 'jornada' not in cols_act:
            conn.execute('ALTER TABLE actividades ADD COLUMN jornada TEXT DEFAULT "Mañana"')
            conn.execute('UPDATE actividades SET jornada="Mañana" WHERE jornada IS NULL OR jornada=""')
            conn.commit()

        cols_ev = [r[1] for r in conn.execute('PRAGMA table_info(evaluaciones)').fetchall()]
        if 'periodo' not in cols_ev:
            conn.execute('ALTER TABLE evaluaciones ADD COLUMN periodo INTEGER DEFAULT 1')
            conn.commit()
        if 'jornada' not in cols_ev:
            conn.execute('ALTER TABLE evaluaciones ADD COLUMN jornada TEXT DEFAULT "Mañana"')
            conn.execute('UPDATE evaluaciones SET jornada="Mañana" WHERE jornada IS NULL OR jornada=""')
            conn.commit()

        cols_comp = [r[1] for r in conn.execute('PRAGMA table_info(compromisos)').fetchall()]
        if 'jornada' not in cols_comp:
            conn.execute('ALTER TABLE compromisos ADD COLUMN jornada TEXT DEFAULT "Mañana"')
            conn.commit()

        cols_hor = [r[1] for r in conn.execute('PRAGMA table_info(horarios_curso)').fetchall()]
        if 'jornada' not in cols_hor:
            conn.execute('ALTER TABLE horarios_curso ADD COLUMN jornada TEXT DEFAULT "Mañana"')
            conn.commit()

        tablas = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if 'asignaciones_materia' not in tablas:
            conn.execute('''CREATE TABLE asignaciones_materia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profesor_id INTEGER NOT NULL, materia TEXT NOT NULL, jornada TEXT NOT NULL,
                UNIQUE(profesor_id, materia, jornada))''')
            conn.commit()
        if 'asignaciones_curso' not in tablas:
            conn.execute('''CREATE TABLE asignaciones_curso (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profesor_id INTEGER NOT NULL, materia TEXT NOT NULL,
                jornada TEXT NOT NULL, curso TEXT NOT NULL,
                UNIQUE(profesor_id, materia, jornada, curso))''')
            conn.commit()
        if 'horarios_curso' not in tablas:
            conn.execute('''CREATE TABLE horarios_curso (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                curso TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT "Mañana",
                dia TEXT NOT NULL, franja TEXT NOT NULL,
                num TEXT DEFAULT "", materia TEXT DEFAULT "", profesor TEXT DEFAULT "",
                UNIQUE(curso, jornada, dia, franja))''')
            conn.commit()
        if 'directoras' not in tablas:
            conn.execute('''CREATE TABLE directoras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL, usuario TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL, curso TEXT NOT NULL,
                jornada TEXT NOT NULL DEFAULT "Mañana",
                email TEXT DEFAULT "", activo INTEGER DEFAULT 1,
                pregunta_secreta TEXT DEFAULT "",
                respuesta_secreta TEXT DEFAULT "")''')
            conn.commit()

        try:
            conn.execute('INSERT OR IGNORE INTO horarios_curso (curso,jornada,dia,franja) VALUES ("__test__","__test__","__test__","__test__")')
            conn.execute('DELETE FROM horarios_curso WHERE curso="__test__"')
            conn.commit()
        except:
            conn.execute('ALTER TABLE horarios_curso RENAME TO horarios_curso_old')
            conn.execute('''CREATE TABLE horarios_curso (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                curso TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT "Mañana",
                dia TEXT NOT NULL, franja TEXT NOT NULL,
                num TEXT DEFAULT "", materia TEXT DEFAULT "", profesor TEXT DEFAULT "",
                UNIQUE(curso, jornada, dia, franja))''')
            conn.execute('INSERT OR IGNORE INTO horarios_curso SELECT * FROM horarios_curso_old')
            conn.execute('DROP TABLE horarios_curso_old')
            conn.commit()

        profs = conn.execute('SELECT id FROM profesores').fetchall()
        for p in profs:
            combos = conn.execute(
                'SELECT DISTINCT materia, jornada, curso FROM actividades WHERE profesor_id=?',
                (p['id'],)
            ).fetchall()
            for c in combos:
                conn.execute('INSERT OR IGNORE INTO asignaciones_materia (profesor_id,materia,jornada) VALUES (?,?,?)',
                             (p['id'], c['materia'], c['jornada']))
                conn.execute('INSERT OR IGNORE INTO asignaciones_curso (profesor_id,materia,jornada,curso) VALUES (?,?,?,?)',
                             (p['id'], c['materia'], c['jornada'], c['curso']))
        conn.commit()

    except Exception as e:
        logger.error(f'[{slug}] Error en migración: {e}')
    finally:
        conn.close()

def init_db(slug):
    conn = conectar(slug)
    stmts = [
        '''CREATE TABLE IF NOT EXISTS profesores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL, usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, activo INTEGER DEFAULT 1,
            email TEXT DEFAULT '', telefono TEXT DEFAULT '',
            pregunta_secreta TEXT DEFAULT '', respuesta_secreta TEXT DEFAULT '')''',
        '''CREATE TABLE IF NOT EXISTS asignaciones_materia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profesor_id INTEGER NOT NULL, materia TEXT NOT NULL, jornada TEXT NOT NULL,
            UNIQUE(profesor_id, materia, jornada))''',
        '''CREATE TABLE IF NOT EXISTS asignaciones_curso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profesor_id INTEGER NOT NULL, materia TEXT NOT NULL,
            jornada TEXT NOT NULL, curso TEXT NOT NULL,
            UNIQUE(profesor_id, materia, jornada, curso))''',
        '''CREATE TABLE IF NOT EXISTS alumnos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL, curso TEXT NOT NULL,
            jornada TEXT NOT NULL DEFAULT "Mañana",
            num_curso INTEGER DEFAULT 0, activo INTEGER DEFAULT 1,
            email_acudiente TEXT DEFAULT '')''',
        '''CREATE TABLE IF NOT EXISTS asistencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aid INTEGER, fecha TEXT, estado TEXT)''',
        '''CREATE TABLE IF NOT EXISTS compromisos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT, fecha TEXT, materia TEXT,
            curso TEXT, jornada TEXT DEFAULT "Mañana")''',
        '''CREATE TABLE IF NOT EXISTS observaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aid INTEGER, materia TEXT, texto TEXT, fecha TEXT)''',
        '''CREATE TABLE IF NOT EXISTS actividades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profesor_id INTEGER NOT NULL, materia TEXT NOT NULL,
            jornada TEXT NOT NULL DEFAULT "Mañana",
            curso TEXT NOT NULL, nombre TEXT NOT NULL,
            orden INTEGER DEFAULT 0, periodo INTEGER DEFAULT 1)''',
        '''CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aid INTEGER NOT NULL, actividad_id INTEGER NOT NULL, val REAL NOT NULL,
            UNIQUE(aid,actividad_id))''',
        '''CREATE TABLE IF NOT EXISTS evaluaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aid INTEGER NOT NULL, profesor_id INTEGER NOT NULL,
            materia TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT "Mañana",
            evaluacion REAL, autoevaluacion REAL, periodo INTEGER DEFAULT 1,
            UNIQUE(aid,profesor_id,materia,jornada,periodo))''',
        '''CREATE TABLE IF NOT EXISTS horarios_curso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            curso TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT "Mañana",
            dia TEXT NOT NULL, franja TEXT NOT NULL,
            num TEXT DEFAULT '', materia TEXT DEFAULT '', profesor TEXT DEFAULT '',
            UNIQUE(curso, jornada, dia, franja))''',
        '''CREATE TABLE IF NOT EXISTS directoras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL, usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, curso TEXT NOT NULL,
            jornada TEXT NOT NULL DEFAULT "Mañana",
            email TEXT DEFAULT '', activo INTEGER DEFAULT 1,
            pregunta_secreta TEXT DEFAULT '',
            respuesta_secreta TEXT DEFAULT '')''',
    ]
    for s in stmts:
        conn.execute(s)
    conn.commit()
    conn.close()
    migrar_db(slug)

# ── HELPERS ───────────────────────────────────────────────────────────────────
def get_profesor(slug):
    pid = session.get(f'profesor_id_{slug}')
    if not pid: return None
    conn = conectar(slug)
    p = conn.execute('SELECT * FROM profesores WHERE id=?', (pid,)).fetchone()
    conn.close()
    return p

def get_sesion_jornada_materia(slug):
    return (session.get(f'jornada_{slug}'), session.get(f'materia_{slug}'))

def get_materias_profesor(slug, pid):
    conn = conectar(slug)
    rows = conn.execute(
        'SELECT materia, jornada FROM asignaciones_materia WHERE profesor_id=? ORDER BY jornada, materia',
        (pid,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_cursos_profesor(slug, pid, materia, jornada):
    conn = conectar(slug)
    rows = conn.execute(
        'SELECT curso FROM asignaciones_curso WHERE profesor_id=? AND materia=? AND jornada=? ORDER BY curso',
        (pid, materia, jornada)
    ).fetchall()
    conn.close()
    return [r['curso'] for r in rows]

def require_colegio(slug):
    if not get_colegio(slug): abort(404)
    if not colegio_activo(slug): abort(403)

# ── PDF REUTILIZABLE ──────────────────────────────────────────────────────────
def generar_pdf_alumno(alumno, slug, colegio, curso, jornada, periodo, conn):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm

    lista_materias = [r['materia'] for r in conn.execute(
        'SELECT DISTINCT materia FROM actividades WHERE curso=? AND jornada=? AND COALESCE(periodo,1)=? ORDER BY materia',
        (curso, jornada, periodo)
    ).fetchall()]

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('t', fontSize=16, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#6c63ff'), spaceAfter=4)
    sub_style    = ParagraphStyle('s', fontSize=10, fontName='Helvetica',
                                  textColor=colors.grey, spaceAfter=10)
    mat_style    = ParagraphStyle('m', fontSize=11, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#6c63ff'), spaceBefore=10, spaceAfter=4)
    story = []
    story.append(Paragraph('LUMINI', titulo_style))
    story.append(Paragraph(
        f'Boletín — {colegio["nombre"] if colegio else slug} · {jornada} · Periodo {periodo}', sub_style))
    story.append(Paragraph(f'Estudiante: {alumno["nombre"]}   |   Curso: {curso}', styles['Normal']))
    story.append(Spacer(1, 0.4*cm))

    todos_finales = []
    for mat in lista_materias:
        notas_r = conn.execute(
            '''SELECT n.val FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
               WHERE n.aid=? AND ac.materia=? AND ac.curso=? AND ac.jornada=?
               AND COALESCE(ac.periodo,1)=?''',
            (alumno['id'], mat, curso, jornada, periodo)
        ).fetchall()
        ev = conn.execute(
            '''SELECT evaluacion, autoevaluacion FROM evaluaciones
               WHERE aid=? AND materia=? AND jornada=? AND COALESCE(periodo,1)=?''',
            (alumno['id'], mat, jornada, periodo)
        ).fetchone()
        act_prom = round(sum(r['val'] for r in notas_r) / len(notas_r), 2) if notas_r else None
        eval_v   = ev['evaluacion']     if ev and ev['evaluacion']     is not None else None
        auto_v   = ev['autoevaluacion'] if ev and ev['autoevaluacion'] is not None else None

        if act_prom is not None or eval_v is not None or auto_v is not None:
            total_peso = 0; nota_final = 0
            if act_prom is not None: nota_final += act_prom * 0.65; total_peso += 0.65
            if eval_v   is not None: nota_final += eval_v   * 0.25; total_peso += 0.25
            if auto_v   is not None: nota_final += auto_v   * 0.10; total_peso += 0.10
            final = round(nota_final / total_peso, 2) if total_peso else None
        else:
            final = None

        story.append(Paragraph(mat, mat_style))
        data = [['Actividades', 'Evaluación', 'Autoevaluación', 'Nota Final'],
                [str(act_prom) if act_prom is not None else '—',
                 str(eval_v)   if eval_v   is not None else '—',
                 str(auto_v)   if auto_v   is not None else '—',
                 str(final)    if final    is not None else '—']]
        t = Table(data, colWidths=[4*cm, 3.5*cm, 3.5*cm, 3*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c63ff')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, -1), 9),
            ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
            ('GRID',       (0, 0), (-1, -1), 0.3, colors.HexColor('#cccccc')),
        ]))
        story.append(t)
        if final is not None: todos_finales.append(final)

    prom_general = round(sum(todos_finales) / len(todos_finales), 2) if todos_finales else 0
    story.append(Spacer(1, 0.5*cm))
    resumen = Table(
        [['PROMEDIO GENERAL', str(prom_general), 'ESTADO',
          'Aprobado' if prom_general >= 3.0 else 'Reprobado']],
        colWidths=[5*cm, 3*cm, 3*cm, 3*cm]
    )
    resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1),
         colors.HexColor('#6c63ff') if prom_general >= 3.0 else colors.HexColor('#e74c3c')),
        ('TEXTCOLOR',  (0, 0), (-1, -1), colors.white),
        ('FONTNAME',   (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 11),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(resumen)
    story.append(Spacer(1, 1*cm))
    doc.build(story)
    buf.seek(0)
    return buf.read(), prom_general

# ── ENVIAR CORREO ─────────────────────────────────────────────────────────────
def enviar_correo(destino, asunto, cuerpo_html):
    if not SENDGRID_API_KEY:
        logger.error('Intento de envío sin SENDGRID_API_KEY configurado.')
        return False
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        mensaje = Mail(from_email=EMAIL_ORIGEN, to_emails=destino,
                       subject=asunto, html_content=cuerpo_html)
        sg.client.mail.send.post(request_body=mensaje.get())
        return True
    except Exception as e:
        logger.error(f'Error al enviar correo a {destino}: {e}')
        return False

# ── ADMIN ─────────────────────────────────────────────────────────────────────
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    error = exito = None
    ip = request.remote_addr

    if not session.get('admin_auth'):
        if request.method == 'POST' and request.form.get('accion') == 'admin_login':
            bloqueado = ip_bloqueada(ip, prefijo='admin')
            if bloqueado:
                error = f'Demasiados intentos. Espera {bloqueado}s.'
                return render_template('admin_login.html', error=error)
            if request.form.get('password', '') == ADMIN_PASSWORD:
                session.permanent = True
                session['admin_auth'] = True
                limpiar_intentos(ip, prefijo='admin')
                logger.info(f'Admin login exitoso desde {ip}')
                return redirect(url_for('admin'))
            registrar_fallo(ip, prefijo='admin')
            logger.warning(f'Admin login fallido desde {ip}')
            error = 'Contraseña incorrecta.'
        return render_template('admin_login.html', error=error)

    conn = conectar_master()
    colegios = conn.execute('SELECT * FROM colegios ORDER BY creado DESC').fetchall()
    conn.close()

    if request.method == 'POST':
        accion = request.form.get('accion')

        if accion == 'crear_colegio':
            nombre   = request.form.get('nombre', '').strip()
            slug     = request.form.get('slug', '').strip().lower().replace(' ', '-')
            num_p    = request.form.get('num_periodos', 4, type=int)
            venc     = request.form.get('vencimiento', '').strip() or None
            codigo   = request.form.get('codigo_registro', '').strip()
            if not nombre or not slug:
                error = 'Nombre y slug son obligatorios.'
            elif not slug.replace('-', '').isalnum():
                error = 'El slug solo puede tener letras, números y guiones.'
            elif not codigo:
                error = 'El código de invitación es obligatorio.'
            else:
                logo_filename = ''
                if 'logo' in request.files:
                    f = request.files['logo']
                    if f and f.filename:
                        if not extension_permitida(f.filename):
                            error = 'Solo se permiten imágenes (png, jpg, jpeg, gif, webp).'
                        else:
                            ext = f.filename.rsplit('.', 1)[-1].lower()
                            logo_filename = f'{slug}.{ext}'
                            f.save(os.path.join(LOGO_FOLDER, logo_filename))
                if not error:
                    try:
                        cm = conectar_master()
                        cm.execute(
                            'INSERT INTO colegios (slug,nombre,logo,num_periodos,vencimiento,codigo_registro) VALUES (?,?,?,?,?,?)',
                            (slug, nombre, logo_filename, num_p, venc, codigo))
                        cm.commit(); cm.close()
                        init_db(slug)
                        exito = f'Colegio "{nombre}" creado. URL: /{slug}/login · Código: {codigo}'
                        logger.info(f'Colegio creado: {slug}')
                    except sqlite3.IntegrityError:
                        error = f'El slug "{slug}" ya existe.'

        elif accion == 'toggle_colegio':
            slug_t = request.form.get('slug')
            cm = conectar_master()
            actual = cm.execute('SELECT activo FROM colegios WHERE slug=?', (slug_t,)).fetchone()
            if actual:
                cm.execute('UPDATE colegios SET activo=? WHERE slug=?',
                           (0 if actual['activo'] else 1, slug_t))
                cm.commit()
            cm.close()
            return redirect(url_for('admin'))

        elif accion == 'editar_colegio':
            slug_e  = request.form.get('slug')
            nombre  = request.form.get('nombre', '').strip()
            num_p   = request.form.get('num_periodos', 4, type=int)
            venc    = request.form.get('vencimiento', '').strip() or None
            codigo  = request.form.get('codigo_registro', '').strip()
            cm = conectar_master()
            cm.execute('UPDATE colegios SET nombre=?, num_periodos=?, vencimiento=?, codigo_registro=? WHERE slug=?',
                       (nombre, num_p, venc, codigo, slug_e))
            cm.commit()
            if 'logo' in request.files:
                f = request.files['logo']
                if f and f.filename:
                    if not extension_permitida(f.filename):
                        error = 'Solo se permiten imágenes (png, jpg, jpeg, gif, webp).'
                    else:
                        ext = f.filename.rsplit('.', 1)[-1].lower()
                        logo_filename = f'{slug_e}.{ext}'
                        f.save(os.path.join(LOGO_FOLDER, logo_filename))
                        cm.execute('UPDATE colegios SET logo=? WHERE slug=?', (logo_filename, slug_e))
                        cm.commit()
            cm.close()
            exito = f'Colegio "{nombre}" actualizado. Código: {codigo}'

        elif accion == 'eliminar_colegio':
            slug_e = request.form.get('slug')
            cm = conectar_master()
            cm.execute('DELETE FROM colegios WHERE slug=?', (slug_e,))
            cm.commit(); cm.close()
            db = db_path(slug_e)
            if os.path.exists(db): os.rename(db, db + '.bak')
            exito = 'Colegio eliminado.'
            logger.info(f'Colegio eliminado: {slug_e}')

        conn = conectar_master()
        colegios = conn.execute('SELECT * FROM colegios ORDER BY creado DESC').fetchall()
        conn.close()

    return render_template('admin_panel.html', colegios=colegios, error=error, exito=exito)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_auth', None)
    return redirect(url_for('admin'))

# ── RECUPERAR CONTRASEÑA (PROFESORES) ─────────────────────────────────────────
@app.route('/<slug>/recuperar', methods=['GET', 'POST'])
def recuperar_password(slug):
    require_colegio(slug)
    colegio = get_colegio(slug)
    error = exito = None
    pregunta = None
    usuario_val = ''
    paso = 1

    if request.method == 'POST':
        accion      = request.form.get('accion', '')
        usuario_val = request.form.get('usuario', '').strip()

        if accion == 'buscar_usuario':
            conn = conectar(slug)
            prof = conn.execute(
                'SELECT * FROM profesores WHERE usuario=? AND activo=1', (usuario_val,)
            ).fetchone()
            conn.close()
            if not prof:
                error = 'Usuario no encontrado.'
            elif not prof['pregunta_secreta']:
                error = 'Este usuario no tiene pregunta secreta. Contacta al administrador.'
            else:
                pregunta = prof['pregunta_secreta']
                paso = 2

        elif accion == 'cambiar_password':
            respuesta = request.form.get('respuesta', '').strip().lower()
            nueva     = request.form.get('nueva', '').strip()
            confirmar = request.form.get('confirmar', '').strip()
            conn = conectar(slug)
            prof = conn.execute(
                'SELECT * FROM profesores WHERE usuario=? AND activo=1', (usuario_val,)
            ).fetchone()
            if not prof:
                error = 'Usuario no encontrado.'; conn.close()
            elif prof['respuesta_secreta'].lower() != respuesta:
                error = 'Respuesta incorrecta.'
                pregunta = prof['pregunta_secreta']; paso = 2; conn.close()
            elif len(nueva) < 6:
                error = 'Mínimo 6 caracteres.'
                pregunta = prof['pregunta_secreta']; paso = 2; conn.close()
            elif nueva != confirmar:
                error = 'Las contraseñas no coinciden.'
                pregunta = prof['pregunta_secreta']; paso = 2; conn.close()
            else:
                conn.execute('UPDATE profesores SET password=? WHERE id=?',
                             (hash_pw(nueva), prof['id']))
                conn.commit(); conn.close()
                exito = '✅ Contraseña actualizada. Ya puedes ingresar.'

    return render_template('recuperar.html',
                           slug=slug, colegio=colegio, error=error, exito=exito,
                           pregunta=pregunta, usuario_val=usuario_val, paso=paso)

# ── RECUPERAR CONTRASEÑA DIRECTORAS (AJAX) ────────────────────────────────────
@app.route('/<slug>/directora/buscar_usuario_recuperar', methods=['POST'])
def directora_buscar_usuario_recuperar(slug):
    require_colegio(slug)
    usuario = request.form.get('usuario', '').strip()
    conn = conectar(slug)
    d = conn.execute(
        'SELECT * FROM directoras WHERE usuario=? AND activo=1', (usuario,)
    ).fetchone()
    conn.close()
    if not d:
        return jsonify({'ok': False, 'mensaje': 'Usuario no encontrado.'})
    if not d['pregunta_secreta']:
        return jsonify({'ok': False, 'mensaje': 'Este usuario no tiene pregunta secreta. Contacta al administrador.'})
    return jsonify({'ok': True, 'pregunta': d['pregunta_secreta']})

@app.route('/<slug>/directora/cambiar_password_recuperar', methods=['POST'])
def directora_cambiar_password_recuperar(slug):
    require_colegio(slug)
    usuario   = request.form.get('usuario', '').strip()
    respuesta = request.form.get('respuesta', '').strip().lower()
    nueva     = request.form.get('nueva', '').strip()
    conn = conectar(slug)
    d = conn.execute(
        'SELECT * FROM directoras WHERE usuario=? AND activo=1', (usuario,)
    ).fetchone()
    if not d:
        conn.close()
        return jsonify({'ok': False, 'mensaje': 'Usuario no encontrado.'})
    if not d['respuesta_secreta'] or d['respuesta_secreta'].lower() != respuesta:
        conn.close()
        return jsonify({'ok': False, 'mensaje': 'Respuesta incorrecta.'})
    if len(nueva) < 6:
        conn.close()
        return jsonify({'ok': False, 'mensaje': 'Mínimo 6 caracteres.'})
    conn.execute('UPDATE directoras SET password=? WHERE id=?', (hash_pw(nueva), d['id']))
    conn.commit(); conn.close()
    return jsonify({'ok': True, 'mensaje': 'Contraseña actualizada. Ya puedes ingresar.'})

# ── LOGIN ─────────────────────────────────────────────────────────────────────
@app.route('/<slug>/login', methods=['GET', 'POST'])
def login(slug):
    require_colegio(slug)
    migrar_db(slug)
    colegio = get_colegio(slug)
    error = None
    ip = request.remote_addr

    if request.method == 'POST':
        if not validar_csrf():
            error = 'Error de seguridad.'
            return render_template('login_v2.html', error=error, materias=MATERIAS,
                                   jornadas=JORNADAS, preguntas=PREGUNTAS_SECRETAS,
                                   slug=slug, colegio=colegio)
        accion = request.form.get('accion')

        if accion == 'profesor_login':
            bloqueado = ip_bloqueada(ip, prefijo=slug)
            if bloqueado:
                error = f'Demasiados intentos. Espera {bloqueado}s.'
                return render_template('login_v2.html', error=error, materias=MATERIAS,
                                       jornadas=JORNADAS, preguntas=PREGUNTAS_SECRETAS,
                                       slug=slug, colegio=colegio)
            u = request.form.get('usuario', '').strip()
            p = request.form.get('password', '').strip()
            if not p:
                error = 'La contraseña es obligatoria.'
            else:
                conn = conectar(slug)
                prof = conn.execute('SELECT * FROM profesores WHERE usuario=?', (u,)).fetchone()
                if prof and verificar_pw(p, prof['password']):
                    if necesita_rehash(prof['password']):
                        conn.execute('UPDATE profesores SET password=? WHERE id=?',
                                     (hash_pw(p), prof['id']))
                        conn.commit()
                        logger.info(f'Hash migrado para profesor id={prof["id"]} en {slug}')
                    conn.close()
                    session.permanent = True
                    session[f'rol_{slug}']        = 'profesor'
                    session[f'profesor_id_{slug}'] = prof['id']
                    limpiar_intentos(ip, prefijo=slug)
                    return redirect(url_for('seleccionar_jornada', slug=slug))
                conn.close()
                registrar_fallo(ip, prefijo=slug)
                error = 'Usuario o contraseña incorrectos.'

        elif accion == 'profesor_registro':
            nombre       = request.form.get('nombre', '').strip()
            usuario      = request.form.get('reg_usuario', '').strip()
            pw           = request.form.get('reg_password', '').strip()
            email_p      = request.form.get('email_prof', '').strip()
            pregunta     = request.form.get('pregunta_secreta', '').strip()
            respuesta    = request.form.get('respuesta_secreta', '').strip()
            materias_sel = request.form.getlist('materias_sel')
            jornadas_sel = request.form.getlist('jornadas_sel')
            codigo       = request.form.get('codigo_registro', '').strip()
            confirmar    = request.form.get('confirmar_password', '').strip()
            # Validar código POR COLEGIO
            codigo_colegio = get_codigo_registro(slug)
            if pw != confirmar:
                error = 'Las contraseñas no coinciden.'
            elif codigo_colegio and codigo != codigo_colegio:
                error = 'Código de invitación incorrecto.'
            elif not nombre or not usuario or not email_p:
                error = 'Completa todos los campos obligatorios.'
            elif len(pw) < 6:
                error = 'Mínimo 6 caracteres.'
            elif not pregunta or not respuesta:
                error = 'Debes elegir una pregunta secreta y escribir tu respuesta.'
            elif not materias_sel:
                error = 'Agrega al menos una materia con su jornada.'
            else:
                conn = conectar(slug)
                if conn.execute('SELECT 1 FROM profesores WHERE usuario=?', (usuario,)).fetchone():
                    error = 'Ese usuario ya existe.'; conn.close()
                else:
                    cur = conn.execute(
                        '''INSERT INTO profesores
                           (nombre,usuario,password,email,pregunta_secreta,respuesta_secreta)
                           VALUES (?,?,?,?,?,?)''',
                        (nombre, usuario, hash_pw(pw), email_p, pregunta, respuesta.lower()))
                    pid = cur.lastrowid
                    for mat, jor in zip(materias_sel, jornadas_sel):
                        if mat and jor:
                            try:
                                conn.execute(
                                    'INSERT OR IGNORE INTO asignaciones_materia (profesor_id,materia,jornada) VALUES (?,?,?)',
                                    (pid, mat, jor))
                            except: pass
                    conn.commit(); conn.close()
                    error = '✅ Registro exitoso. Ya puedes ingresar.'

        elif accion == 'estudiante':
            nombre  = request.form.get('nombre_est', '').strip().lower()
            jornada = request.form.get('jornada_est', '').strip()
            conn = conectar(slug)
            if jornada:
                alumno = conn.execute(
                    'SELECT * FROM alumnos WHERE LOWER(nombre)=? AND jornada=? AND activo=1',
                    (nombre, jornada)).fetchone()
            else:
                alumno = conn.execute(
                    'SELECT * FROM alumnos WHERE LOWER(nombre)=? AND activo=1', (nombre,)).fetchone()
            conn.close()
            if alumno:
                session.permanent = True
                session[f'rol_{slug}']       = 'estudiante'
                session[f'alumno_id_{slug}'] = alumno['id']
                return redirect(url_for('vista_estudiante', slug=slug))
            error = 'No se encontró ese estudiante.'

        elif accion == 'directora_login':
            u = request.form.get('dir_usuario', '').strip()
            p = request.form.get('dir_password', '').strip()
            conn = conectar(slug)
            d = conn.execute(
                'SELECT * FROM directoras WHERE usuario=? AND activo=1', (u,)).fetchone()
            conn.close()
            if d and verificar_pw(p, d['password']):
                session.permanent = True
                session[f'directora_id_{slug}'] = d['id']
                return redirect(url_for('directora_panel', slug=slug))
            error = 'Usuario o contraseña incorrectos.'

    return render_template('login_v2.html', error=error, materias=MATERIAS,
                           jornadas=JORNADAS, preguntas=PREGUNTAS_SECRETAS,
                           slug=slug, colegio=colegio)

# ── SELECTOR DE JORNADA/MATERIA ───────────────────────────────────────────────
@app.route('/<slug>/seleccionar', methods=['GET', 'POST'])
def seleccionar_jornada(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    colegio = get_colegio(slug)
    materias_jornadas = get_materias_profesor(slug, prof['id'])

    if not materias_jornadas:
        return render_template('seleccionar_jornada.html',
                               slug=slug, colegio=colegio, profesor=prof,
                               materias_jornadas=[],
                               error='No tienes materias asignadas. Contacta al administrador.')

    if request.method == 'POST':
        materia = request.form.get('materia', '').strip()
        jornada = request.form.get('jornada', '').strip()
        if materia and jornada:
            session[f'materia_{slug}'] = materia
            session[f'jornada_{slug}'] = jornada
            return redirect(url_for('home', slug=slug))

    if len(materias_jornadas) == 1:
        session[f'materia_{slug}'] = materias_jornadas[0]['materia']
        session[f'jornada_{slug}'] = materias_jornadas[0]['jornada']
        return redirect(url_for('home', slug=slug))

    return render_template('seleccionar_jornada.html',
                           slug=slug, colegio=colegio, profesor=prof,
                           materias_jornadas=materias_jornadas)

@app.route('/<slug>/logout')
def logout(slug):
    for k in [f'rol_{slug}', f'profesor_id_{slug}', f'alumno_id_{slug}',
              f'materia_{slug}', f'jornada_{slug}']:
        session.pop(k, None)
    return redirect(url_for('login', slug=slug))

# ── HOME ──────────────────────────────────────────────────────────────────────
@app.route('/<slug>/')
@app.route('/<slug>')
def home(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))

    jornada, materia = get_sesion_jornada_materia(slug)
    if not jornada or not materia:
        return redirect(url_for('seleccionar_jornada', slug=slug))

    colegio     = get_colegio(slug)
    mis_cursos  = get_cursos_profesor(slug, prof['id'], materia, jornada)
    curso_sel   = request.args.get('curso', mis_cursos[0] if mis_cursos else None)
    periodo_sel = request.args.get('periodo', 1, type=int)

    conn = conectar(slug)
    alumnos = actividades = agenda = []

    if curso_sel and curso_sel in mis_cursos:
        alumnos = conn.execute(
            'SELECT * FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre COLLATE NOCASE',
            (curso_sel, jornada)).fetchall()
        for i, a in enumerate(alumnos, 1):
            conn.execute('UPDATE alumnos SET num_curso=? WHERE id=?', (i, a['id']))
        conn.commit()
        alumnos = conn.execute(
            'SELECT * FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre COLLATE NOCASE',
            (curso_sel, jornada)).fetchall()
        actividades = conn.execute(
            '''SELECT * FROM actividades
               WHERE profesor_id=? AND materia=? AND jornada=? AND curso=?
               AND COALESCE(periodo,1)=? ORDER BY orden''',
            (prof['id'], materia, jornada, curso_sel, periodo_sel)).fetchall()
        agenda = conn.execute(
            'SELECT * FROM compromisos WHERE materia=? AND curso=? AND jornada=? ORDER BY fecha',
            (materia, curso_sel, jornada)).fetchall()

    MESES = {'01': 'Ene', '02': 'Feb', '03': 'Mar', '04': 'Abr', '05': 'May', '06': 'Jun',
             '07': 'Jul', '08': 'Ago', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dic'}
    datos = []
    for a in alumnos:
        notas_raw = conn.execute(
            '''SELECT n.actividad_id, n.val, n.id FROM notas n
               JOIN actividades ac ON ac.id=n.actividad_id
               WHERE n.aid=? AND ac.materia=? AND ac.jornada=? AND ac.curso=?
               AND COALESCE(ac.periodo,1)=?''',
            (a['id'], materia, jornada, curso_sel, periodo_sel)).fetchall()
        notas_map = {nr['actividad_id']: {'val': nr['val'], 'id': nr['id']} for nr in notas_raw}
        ev = conn.execute(
            '''SELECT evaluacion, autoevaluacion FROM evaluaciones
               WHERE aid=? AND profesor_id=? AND materia=? AND jornada=?
               AND COALESCE(periodo,1)=?''',
            (a['id'], prof['id'], materia, jornada, periodo_sel)).fetchone()
        eval_v = ev['evaluacion']     if ev and ev['evaluacion']     is not None else None
        auto_v = ev['autoevaluacion'] if ev and ev['autoevaluacion'] is not None else None
        todas = [nr['val'] for nr in notas_raw]
        if eval_v is not None: todas.append(eval_v)
        if auto_v is not None: todas.append(auto_v)
        prom = round(sum(todas) / len(todas), 2) if todas else 0
        historial_raw = conn.execute(
            'SELECT fecha, estado FROM asistencia WHERE aid=? ORDER BY fecha', (a['id'],)).fetchall()
        hist_meses = {}
        for h in historial_raw:
            if h['fecha']:
                p2 = h['fecha'].split('-')
                if len(p2) >= 2:
                    label = f"{MESES.get(p2[1], p2[1])} {p2[0]}"
                    hist_meses.setdefault(label, []).append({'fecha': h['fecha'], 'estado': h['estado']})
        asis = conn.execute(
            'SELECT estado FROM asistencia WHERE aid=? ORDER BY id DESC LIMIT 1', (a['id'],)).fetchone()
        obs = conn.execute(
            'SELECT id, materia, texto, fecha FROM observaciones WHERE aid=? AND materia=? ORDER BY fecha DESC',
            (a['id'], materia)).fetchall()
        datos.append({
            'id': a['id'], 'num_curso': a['num_curso'],
            'nombre': a['nombre'], 'curso': a['curso'],
            'promedio': prom, 'notas_map': notas_map,
            'evaluacion':     eval_v if eval_v is not None else '',
            'autoevaluacion': auto_v if auto_v is not None else '',
            'asistencia': asis['estado'] if asis else '-',
            'historial_meses': hist_meses,
            'observaciones': [dict(o) for o in obs],
        })

    prom_gral = round(sum(d['promedio'] for d in datos) / len(datos), 2) if datos else 0
    mejor     = max(datos, key=lambda x: x['promedio'], default={'nombre': 'N/A', 'promedio': 0})
    conn.close()
    num_periodos = int(colegio['num_periodos']) if colegio and colegio['num_periodos'] else 4
    return render_template('index.html',
                           profesor=prof, mis_cursos=mis_cursos, curso_sel=curso_sel,
                           estudiantes=datos, actividades=actividades, compromisos=agenda,
                           prom_general=prom_gral, mejor=mejor, slug=slug, colegio=colegio,
                           num_periodos=num_periodos, periodo_sel=periodo_sel,
                           materia=materia, jornada=jornada,
                           materias_jornadas=get_materias_profesor(slug, prof['id']))

# ── ACTIVIDADES ───────────────────────────────────────────────────────────────
@app.route('/<slug>/nueva_actividad', methods=['POST'])
def nueva_actividad(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    if not validar_csrf(): return ('Error CSRF', 403)
    jornada, materia = get_sesion_jornada_materia(slug)
    nombre    = request.form.get('nombre', '').strip()
    curso_sel = request.form.get('curso_sel', '')
    periodo   = request.form.get('periodo_sel', 1, type=int)
    if nombre and curso_sel and materia and jornada:
        conn = conectar(slug)
        max_ord = conn.execute(
            '''SELECT COALESCE(MAX(orden),0) FROM actividades
               WHERE profesor_id=? AND materia=? AND jornada=? AND curso=?
               AND COALESCE(periodo,1)=?''',
            (prof['id'], materia, jornada, curso_sel, periodo)).fetchone()[0]
        conn.execute(
            'INSERT INTO actividades (profesor_id,materia,jornada,curso,nombre,orden,periodo) VALUES (?,?,?,?,?,?,?)',
            (prof['id'], materia, jornada, curso_sel, nombre, max_ord + 1, periodo))
        conn.commit(); conn.close()
    return redirect(url_for('home', slug=slug, curso=curso_sel, periodo=periodo))

@app.route('/<slug>/borrar_actividad/<int:act_id>')
def borrar_actividad(slug, act_id):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    conn = conectar(slug)
    act = conn.execute('SELECT profesor_id, curso FROM actividades WHERE id=?', (act_id,)).fetchone()
    curso = ''
    if act and act['profesor_id'] == prof['id']:
        conn.execute('DELETE FROM notas WHERE actividad_id=?', (act_id,))
        conn.execute('DELETE FROM actividades WHERE id=?', (act_id,))
        conn.commit(); curso = act['curso']
    conn.close()
    return redirect(url_for('home', slug=slug, curso=curso))

# ── NOTAS ─────────────────────────────────────────────────────────────────────
@app.route('/<slug>/guardar_nota', methods=['POST'])
def guardar_nota(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return ('', 403)
    if not validar_csrf(): return ('Error CSRF', 403)
    aid          = request.form.get('aid', type=int)
    actividad_id = request.form.get('actividad_id', type=int)
    val          = request.form.get('val', type=float)
    if None in (aid, actividad_id, val): return ('', 400)
    conn = conectar(slug)
    act = conn.execute('SELECT id FROM actividades WHERE id=?', (actividad_id,)).fetchone()
    if act:
        conn.execute(
            '''INSERT INTO notas (aid,actividad_id,val) VALUES (?,?,?)
               ON CONFLICT(aid,actividad_id) DO UPDATE SET val=excluded.val''',
            (aid, actividad_id, val))
        conn.commit()
    conn.close()
    return ('', 204)

# ── EVALUACIONES ──────────────────────────────────────────────────────────────
@app.route('/<slug>/guardar_evaluacion', methods=['POST'])
def guardar_evaluacion(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return ('', 403)
    if not validar_csrf(): return ('Error CSRF', 403)
    jornada, materia = get_sesion_jornada_materia(slug)
    aid     = request.form.get('aid', type=int)
    ev      = request.form.get('evaluacion', type=float)
    au      = request.form.get('autoevaluacion', type=float)
    periodo = request.form.get('periodo', 1, type=int)
    if aid is None: return ('', 400)
    conn = conectar(slug)
    conn.execute(
        '''INSERT OR REPLACE INTO evaluaciones
           (aid,profesor_id,materia,jornada,evaluacion,autoevaluacion,periodo)
           VALUES (?,?,?,?,?,?,?)''',
        (aid, prof['id'], materia, jornada, ev, au, periodo))
    conn.commit(); conn.close()
    return ('', 204)

# ── AGENDA ────────────────────────────────────────────────────────────────────
@app.route('/<slug>/nuevo_trabajo', methods=['POST'])
def nuevo_trabajo(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    if not validar_csrf(): return ('Error CSRF', 403)
    jornada, materia = get_sesion_jornada_materia(slug)
    curso_sel = request.form.get('curso_sel', '')
    conn = conectar(slug)
    conn.execute('INSERT INTO compromisos (titulo,fecha,materia,curso,jornada) VALUES (?,?,?,?,?)',
                 (request.form.get('titulo'), request.form.get('fecha'), materia, curso_sel, jornada))
    conn.commit(); conn.close()
    return redirect(url_for('home', slug=slug, curso=curso_sel))

@app.route('/<slug>/borrar_trabajo/<int:id_t>')
def borrar_trabajo(slug, id_t):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    jornada, materia = get_sesion_jornada_materia(slug)
    conn = conectar(slug)
    c = conn.execute('SELECT curso FROM compromisos WHERE id=?', (id_t,)).fetchone()
    curso = c['curso'] if c else ''
    conn.execute('DELETE FROM compromisos WHERE id=? AND materia=?', (id_t, materia))
    conn.commit(); conn.close()
    return redirect(url_for('home', slug=slug, curso=curso))

# ── ALUMNOS ───────────────────────────────────────────────────────────────────
@app.route('/<slug>/registrar', methods=['POST'])
def registrar(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    if not validar_csrf(): return ('Error CSRF', 403)
    jornada, materia = get_sesion_jornada_materia(slug)
    nom       = request.form.get('nombre', '').strip()
    cur       = request.form.get('curso', '').strip()
    curso_sel = request.form.get('curso_sel', cur)
    if nom and cur and jornada:
        conn = conectar(slug)
        with conn:
            conn.execute(
                'INSERT INTO alumnos (nombre,curso,jornada,num_curso,activo) VALUES (?,?,?,0,1)',
                (nom, cur, jornada))
            todos = conn.execute(
                'SELECT id FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre COLLATE NOCASE',
                (cur, jornada)).fetchall()
            for i, a in enumerate(todos, 1):
                conn.execute('UPDATE alumnos SET num_curso=? WHERE id=?', (i, a['id']))
        conn.close()
    return redirect(url_for('home', slug=slug, curso=curso_sel))

@app.route('/<slug>/archivar_alumno/<int:id>')
def archivar_alumno(slug, id):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    curso_sel = request.args.get('curso', '')
    conn = conectar(slug)
    conn.execute('UPDATE alumnos SET activo=0 WHERE id=?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('home', slug=slug, curso=curso_sel))

@app.route('/<slug>/reactivar_alumno/<int:id>')
def reactivar_alumno(slug, id):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    curso_sel = request.args.get('curso', '')
    conn = conectar(slug)
    conn.execute('UPDATE alumnos SET activo=1 WHERE id=?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('archivados', slug=slug, curso=curso_sel))

@app.route('/<slug>/eliminar_alumno/<int:id>')
def eliminar_alumno(slug, id):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    curso_sel = request.args.get('curso', '')
    conn = conectar(slug)
    conn.execute('DELETE FROM alumnos WHERE id=?', (id,))
    conn.execute('DELETE FROM notas WHERE aid=?', (id,))
    conn.execute('DELETE FROM evaluaciones WHERE aid=?', (id,))
    conn.execute('DELETE FROM asistencia WHERE aid=?', (id,))
    conn.execute('DELETE FROM observaciones WHERE aid=?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('archivados', slug=slug, curso=curso_sel))

# ── ARCHIVADOS ────────────────────────────────────────────────────────────────
@app.route('/<slug>/archivados')
def archivados(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    jornada, materia = get_sesion_jornada_materia(slug)
    colegio    = get_colegio(slug)
    mis_cursos = get_cursos_profesor(slug, prof['id'], materia, jornada)
    curso_sel  = request.args.get('curso', mis_cursos[0] if mis_cursos else None)
    conn = conectar(slug)
    alumnos_arch = []
    if curso_sel:
        alumnos_arch = conn.execute(
            'SELECT * FROM alumnos WHERE curso=? AND jornada=? AND activo=0 ORDER BY nombre COLLATE NOCASE',
            (curso_sel, jornada)).fetchall()
    profs_arch = conn.execute(
        'SELECT * FROM profesores WHERE activo=0 ORDER BY nombre COLLATE NOCASE').fetchall()
    profs_raw = conn.execute(
        'SELECT * FROM profesores WHERE activo=1 ORDER BY nombre COLLATE NOCASE').fetchall()
    profesores_activos = []
    for p in profs_raw:
        mjs = conn.execute(
            'SELECT materia, jornada FROM asignaciones_materia WHERE profesor_id=? ORDER BY jornada, materia',
            (p['id'],)).fetchall()
        cursos_info = []
        for mj in mjs:
            cursos = conn.execute(
                'SELECT curso FROM asignaciones_curso WHERE profesor_id=? AND materia=? AND jornada=?',
                (p['id'], mj['materia'], mj['jornada'])).fetchall()
            for c in cursos:
                cursos_info.append({'curso': c['curso'], 'materia': mj['materia'], 'jornada': mj['jornada']})
        otros_profesores = []
        for mj in mjs:
            otros = conn.execute(
                '''SELECT p2.id, p2.nombre, am.materia, am.jornada
                   FROM profesores p2
                   JOIN asignaciones_materia am ON am.profesor_id=p2.id
                   WHERE am.materia=? AND am.jornada=? AND p2.id!=? AND p2.activo=1''',
                (mj['materia'], mj['jornada'], p['id'])).fetchall()
            for o in otros:
                entry = {'id': o['id'], 'nombre': o['nombre'], 'materia': o['materia'], 'jornada': o['jornada']}
                if entry not in otros_profesores:
                    otros_profesores.append(entry)
        profesores_activos.append({
            'id': p['id'], 'nombre': p['nombre'], 'usuario': p['usuario'],
            'email': p['email'] or '',
            'materias_jornadas': [dict(mj) for mj in mjs],
            'cursos_info': cursos_info,
            'otros_profesores': otros_profesores,
        })
    conn.close()
    return render_template('archivados.html',
                           slug=slug, colegio=colegio, profesor=prof,
                           mis_cursos=mis_cursos, curso_sel=curso_sel,
                           alumnos_archivados=alumnos_arch,
                           profesores_archivados=profs_arch,
                           profesores_activos=profesores_activos)

@app.route('/<slug>/archivar_profesor/<int:id>')
def archivar_profesor(slug, id):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    conn = conectar(slug)
    conn.execute('UPDATE profesores SET activo=0 WHERE id=?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('archivados', slug=slug))

@app.route('/<slug>/archivar_profesor_con_reasignacion', methods=['POST'])
def archivar_profesor_con_reasignacion(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return jsonify({'ok': False, 'mensaje': 'No autorizado'})
    if not validar_csrf(): return jsonify({'ok': False, 'mensaje': 'Error CSRF'})
    profesor_id      = request.form.get('profesor_id', type=int)
    prof_destino_id  = request.form.get('prof_destino_id', type=int)
    cursos_reasignar = request.form.getlist('cursos_reasignar')
    if not profesor_id:
        return jsonify({'ok': False, 'mensaje': 'Datos incompletos.'})
    conn = conectar(slug)
    try:
        if prof_destino_id and cursos_reasignar:
            for item in cursos_reasignar:
                partes = item.split('|')
                if len(partes) != 3: continue
                curso, mat, jor = partes
                conn.execute(
                    '''UPDATE actividades SET profesor_id=?
                       WHERE profesor_id=? AND materia=? AND jornada=? AND curso=?''',
                    (prof_destino_id, profesor_id, mat, jor, curso))
                conn.execute(
                    '''UPDATE evaluaciones SET profesor_id=?
                       WHERE profesor_id=? AND materia=? AND jornada=?
                       AND aid IN (SELECT id FROM alumnos WHERE curso=? AND jornada=?)''',
                    (prof_destino_id, profesor_id, mat, jor, curso, jor))
                conn.execute(
                    'INSERT OR IGNORE INTO asignaciones_curso (profesor_id,materia,jornada,curso) VALUES (?,?,?,?)',
                    (prof_destino_id, mat, jor, curso))
                conn.execute(
                    'DELETE FROM asignaciones_curso WHERE profesor_id=? AND materia=? AND jornada=? AND curso=?',
                    (profesor_id, mat, jor, curso))
                conn.execute(
                    'INSERT OR IGNORE INTO asignaciones_materia (profesor_id,materia,jornada) VALUES (?,?,?)',
                    (prof_destino_id, mat, jor))
        conn.execute('UPDATE profesores SET activo=0 WHERE id=?', (profesor_id,))
        conn.commit()
        return jsonify({'ok': True, 'mensaje': 'Profesor archivado correctamente.'})
    except Exception as e:
        conn.rollback()
        logger.error(f'Error al archivar profesor {profesor_id} en {slug}: {e}')
        return jsonify({'ok': False, 'mensaje': str(e)})
    finally:
        conn.close()

@app.route('/<slug>/reactivar_profesor/<int:id>')
def reactivar_profesor(slug, id):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    conn = conectar(slug)
    conn.execute('UPDATE profesores SET activo=1 WHERE id=?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('archivados', slug=slug))

@app.route('/<slug>/eliminar_profesor/<int:id>')
def eliminar_profesor(slug, id):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    conn = conectar(slug)
    conn.execute('DELETE FROM profesores WHERE id=?', (id,))
    conn.execute('DELETE FROM asignaciones_materia WHERE profesor_id=?', (id,))
    conn.execute('DELETE FROM asignaciones_curso WHERE profesor_id=?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('archivados', slug=slug))

# ── ASISTENCIA ────────────────────────────────────────────────────────────────
@app.route('/<slug>/marcar_asistencia', methods=['POST'])
def marcar_asistencia(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return ('', 403)
    if not validar_csrf(): return ('Error CSRF', 403)
    aid    = request.form.get('aid')
    estado = request.form.get('estado')
    conn = conectar(slug)
    conn.execute('INSERT INTO asistencia (aid,fecha,estado) VALUES (?,date("now"),?)', (aid, estado))
    conn.commit(); conn.close()
    return ('', 204)

# ── OBSERVACIONES ─────────────────────────────────────────────────────────────
@app.route('/<slug>/agregar_observacion', methods=['POST'])
def agregar_observacion(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return ('', 403)
    if not validar_csrf(): return ('Error CSRF', 403)
    jornada, materia = get_sesion_jornada_materia(slug)
    texto = request.form.get('texto', '').strip()
    aid   = request.form.get('aid')
    if not texto: return ('', 400)
    conn = conectar(slug)
    conn.execute('INSERT INTO observaciones (aid,materia,texto,fecha) VALUES (?,?,?,date("now"))',
                 (aid, materia, texto))
    conn.commit()
    obs = conn.execute(
        'SELECT id, materia, texto, fecha FROM observaciones WHERE aid=? AND materia=? ORDER BY id DESC LIMIT 1',
        (aid, materia)).fetchone()
    conn.close()
    return jsonify({'id': obs['id'], 'materia': obs['materia'],
                    'texto': obs['texto'], 'fecha': obs['fecha']})

@app.route('/<slug>/borrar_observacion/<int:id_o>', methods=['POST'])
def borrar_observacion(slug, id_o):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return ('', 403)
    if not validar_csrf(): return ('Error CSRF', 403)
    jornada, materia = get_sesion_jornada_materia(slug)
    conn = conectar(slug)
    obs = conn.execute('SELECT materia FROM observaciones WHERE id=?', (id_o,)).fetchone()
    if obs and obs['materia'] == materia:
        conn.execute('DELETE FROM observaciones WHERE id=?', (id_o,))
        conn.commit()
    conn.close()
    return ('', 204)

# ── PERFIL / CURSOS ───────────────────────────────────────────────────────────
@app.route('/<slug>/cambiar_password', methods=['GET', 'POST'])
def cambiar_password(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    jornada, materia = get_sesion_jornada_materia(slug)
    error = exito = None
    if request.method == 'POST':
        if not validar_csrf():
            error = 'Error de seguridad.'
        else:
            actual    = request.form.get('actual', '').strip()
            nueva     = request.form.get('nueva', '').strip()
            confirmar = request.form.get('confirmar', '').strip()
            if not verificar_pw(actual, prof['password']):
                error = 'Contraseña actual incorrecta.'
            elif len(nueva) < 6:
                error = 'Mínimo 6 caracteres.'
            elif nueva != confirmar:
                error = 'Las contraseñas no coinciden.'
            else:
                conn = conectar(slug)
                conn.execute('UPDATE profesores SET password=? WHERE id=?',
                             (hash_pw(nueva), prof['id']))
                conn.commit(); conn.close()
                exito = '¡Contraseña cambiada!'
    mis_cursos        = get_cursos_profesor(slug, prof['id'], materia, jornada)
    materias_jornadas = get_materias_profesor(slug, prof['id'])
    colegio           = get_colegio(slug)
    return render_template('cambiar_password.html',
                           profesor=prof, mis_cursos=mis_cursos,
                           materias_jornadas=materias_jornadas,
                           error=error, exito=exito, slug=slug, colegio=colegio,
                           materia=materia, jornada=jornada)

@app.route('/<slug>/agregar_cursos', methods=['POST'])
def agregar_cursos(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    jornada, materia = get_sesion_jornada_materia(slug)
    cursos = request.form.getlist('cursos')
    extra  = request.form.get('cursos_extra', '').strip()
    if extra: cursos += [c.strip() for c in extra.split(',') if c.strip()]
    conn = conectar(slug)
    for c in cursos:
        if c:
            conn.execute(
                'INSERT OR IGNORE INTO asignaciones_curso (profesor_id,materia,jornada,curso) VALUES (?,?,?,?)',
                (prof['id'], materia, jornada, c))
    conn.commit(); conn.close()
    return redirect(url_for('cambiar_password', slug=slug))

@app.route('/<slug>/quitar_curso/<curso>')
def quitar_curso(slug, curso):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    jornada, materia = get_sesion_jornada_materia(slug)
    conn = conectar(slug)
    conn.execute(
        'DELETE FROM asignaciones_curso WHERE profesor_id=? AND materia=? AND jornada=? AND curso=?',
        (prof['id'], materia, jornada, curso))
    conn.commit(); conn.close()
    return redirect(url_for('cambiar_password', slug=slug))

# ── TRANSFERIR CURSO ──────────────────────────────────────────────────────────
@app.route('/<slug>/transferir_curso', methods=['GET', 'POST'])
def transferir_curso(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    jornada, materia = get_sesion_jornada_materia(slug)
    if not jornada or not materia:
        return redirect(url_for('seleccionar_jornada', slug=slug))
    colegio    = get_colegio(slug)
    error = exito = None
    mis_cursos = get_cursos_profesor(slug, prof['id'], materia, jornada)
    conn = conectar(slug)
    profesores_destino = conn.execute(
        '''SELECT p.id, p.nombre FROM profesores p
           JOIN asignaciones_materia am ON am.profesor_id=p.id
           WHERE am.materia=? AND am.jornada=? AND p.id!=? AND p.activo=1
           ORDER BY p.nombre''',
        (materia, jornada, prof['id'])).fetchall()
    num_periodos = int(colegio['num_periodos']) if colegio and colegio['num_periodos'] else 4
    conn.close()

    if request.method == 'POST':
        if not validar_csrf():
            error = 'Error de seguridad.'
        else:
            accion           = request.form.get('accion', '')
            curso_transferir = request.form.get('curso', '').strip()
            periodos_str     = request.form.get('periodos', '')
            periodos         = [p for p in periodos_str.split(',') if p.strip()]
            if not curso_transferir:
                error = 'Selecciona un curso.'
            elif not periodos:
                error = 'Selecciona al menos un periodo.'
            elif curso_transferir not in mis_cursos:
                error = 'Ese curso no te pertenece.'
            else:
                conn = conectar(slug)
                if accion == 'transferir':
                    prof_destino_id = request.form.get('profesor_destino_id', type=int)
                    if not prof_destino_id:
                        error = 'Selecciona un profesor destino.'; conn.close()
                    else:
                        for p in periodos:
                            p = int(p)
                            conn.execute(
                                '''UPDATE actividades SET profesor_id=?
                                   WHERE profesor_id=? AND materia=? AND jornada=?
                                   AND curso=? AND COALESCE(periodo,1)=?''',
                                (prof_destino_id, prof['id'], materia, jornada, curso_transferir, p))
                            conn.execute(
                                '''UPDATE evaluaciones SET profesor_id=?
                                   WHERE profesor_id=? AND materia=? AND jornada=?
                                   AND COALESCE(periodo,1)=?
                                   AND aid IN (SELECT id FROM alumnos WHERE curso=? AND jornada=?)''',
                                (prof_destino_id, prof['id'], materia, jornada,
                                 p, curso_transferir, jornada))
                        conn.execute(
                            'INSERT OR IGNORE INTO asignaciones_curso (profesor_id,materia,jornada,curso) VALUES (?,?,?,?)',
                            (prof_destino_id, materia, jornada, curso_transferir))
                        conn.execute(
                            'DELETE FROM asignaciones_curso WHERE profesor_id=? AND materia=? AND jornada=? AND curso=?',
                            (prof['id'], materia, jornada, curso_transferir))
                        conn.commit(); conn.close()
                        exito = f'✅ Curso {curso_transferir} transferido correctamente.'
                        mis_cursos = get_cursos_profesor(slug, prof['id'], materia, jornada)
                elif accion == 'archivar_curso':
                    conn.execute(
                        'DELETE FROM asignaciones_curso WHERE profesor_id=? AND materia=? AND jornada=? AND curso=?',
                        (prof['id'], materia, jornada, curso_transferir))
                    conn.commit(); conn.close()
                    exito = f'✅ Curso {curso_transferir} archivado.'
                    mis_cursos = get_cursos_profesor(slug, prof['id'], materia, jornada)
                else:
                    conn.close(); error = 'Acción no reconocida.'

    return render_template('transferir_curso.html',
                           slug=slug, colegio=colegio, profesor=prof,
                           mis_cursos=mis_cursos, profesores_destino=profesores_destino,
                           error=error, exito=exito, materia=materia, jornada=jornada,
                           num_periodos=num_periodos)

# ── HORARIOS ──────────────────────────────────────────────────────────────────
DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']

@app.route('/<slug>/horarios', methods=['GET', 'POST'])
def horarios(slug):
    require_colegio(slug)
    if not session.get(f'rol_{slug}'): return redirect(url_for('login', slug=slug))
    prof    = get_profesor(slug)
    colegio = get_colegio(slug)
    jornada, materia = get_sesion_jornada_materia(slug)
    mis_cursos = get_cursos_profesor(slug, prof['id'], materia, jornada) if prof else []
    curso_sel  = request.args.get('curso', mis_cursos[0] if mis_cursos else None)
    c = conectar(slug)
    if request.method == 'POST':
        dia      = request.form.get('dia', '')
        franja   = request.form.get('franja', '')
        num      = request.form.get('num', '').strip()
        mat      = request.form.get('materia', '').strip()
        profesor = request.form.get('profesor', '').strip()
        curso_p  = request.form.get('curso', curso_sel)
        if mat or profesor:
            c.execute(
                '''INSERT INTO horarios_curso (curso,jornada,dia,franja,num,materia,profesor)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(curso,jornada,dia,franja) DO UPDATE SET
                       num=excluded.num, materia=excluded.materia, profesor=excluded.profesor''',
                (curso_p, jornada, dia, franja, num, mat, profesor))
        else:
            c.execute(
                'DELETE FROM horarios_curso WHERE curso=? AND jornada=? AND dia=? AND franja=?',
                (curso_p, jornada, dia, franja))
        c.commit(); c.close()
        return ('', 204)
    filas = []
    if curso_sel:
        filas = c.execute(
            'SELECT dia, franja, num, materia, profesor FROM horarios_curso WHERE curso=? AND jornada=?',
            (curso_sel, jornada)).fetchall()
    c.close()
    horario_map = {
        f"{r['dia']}_{r['franja']}": {'num': r['num'], 'materia': r['materia'], 'profesor': r['profesor']}
        for r in filas}
    return render_template('horarios.html', slug=slug, colegio=colegio, profesor=prof,
                           mis_cursos=mis_cursos, curso_sel=curso_sel, dias=DIAS_SEMANA,
                           horario_map=horario_map, jornada=jornada)

# ── ESTUDIANTE ────────────────────────────────────────────────────────────────
@app.route('/<slug>/estudiante')
def vista_estudiante(slug):
    require_colegio(slug)
    if session.get(f'rol_{slug}') != 'estudiante':
        return redirect(url_for('login', slug=slug))
    aid     = session.get(f'alumno_id_{slug}')
    colegio = get_colegio(slug)
    conn    = conectar(slug)
    alumno  = conn.execute('SELECT * FROM alumnos WHERE id=? AND activo=1', (aid,)).fetchone()
    if not alumno:
        conn.close()
        session.pop(f'rol_{slug}', None)
        session.pop(f'alumno_id_{slug}', None)
        return redirect(url_for('login', slug=slug))
    agenda = conn.execute(
        'SELECT * FROM compromisos WHERE curso=? AND jornada=? ORDER BY fecha, materia',
        (alumno['curso'], alumno['jornada'])).fetchall()
    notas_raw = conn.execute(
        '''SELECT ac.materia, ac.nombre as act_nombre, n.val
           FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
           WHERE n.aid=? ORDER BY ac.materia, ac.orden''', (aid,)).fetchall()
    evals_raw = conn.execute(
        'SELECT materia, evaluacion, autoevaluacion FROM evaluaciones WHERE aid=?', (aid,)).fetchall()
    evals_map = {e['materia']: dict(e) for e in evals_raw}
    notas_pm = {}
    for nr in notas_raw:
        notas_pm.setdefault(nr['materia'], []).append({'actividad': nr['act_nombre'], 'val': nr['val']})
    for mat in evals_map:
        if mat not in notas_pm: notas_pm[mat] = []
    todos_vals = [n['val'] for v in notas_pm.values() for n in v]
    for e in evals_raw:
        if e['evaluacion']     is not None: todos_vals.append(e['evaluacion'])
        if e['autoevaluacion'] is not None: todos_vals.append(e['autoevaluacion'])
    promedio_general = round(sum(todos_vals) / len(todos_vals), 2) if todos_vals else 0
    asist_raw   = conn.execute(
        'SELECT fecha, estado FROM asistencia WHERE aid=? ORDER BY fecha', (aid,)).fetchall()
    asist_stats = {'P': 0, 'A': 0, 'T': 0, 'total': 0}
    MESES = {'01': 'Ene', '02': 'Feb', '03': 'Mar', '04': 'Abr', '05': 'May', '06': 'Jun',
             '07': 'Jul', '08': 'Ago', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dic'}
    historial_meses = {}
    for h in asist_raw:
        asist_stats[h['estado']] = asist_stats.get(h['estado'], 0) + 1
        asist_stats['total'] += 1
        if h['fecha']:
            p = h['fecha'].split('-')
            if len(p) >= 2:
                label = f"{MESES.get(p[1], p[1])} {p[0]}"
                historial_meses.setdefault(label, []).append({'fecha': h['fecha'], 'estado': h['estado']})
    observaciones = conn.execute(
        'SELECT materia, texto, fecha FROM observaciones WHERE aid=? ORDER BY fecha DESC', (aid,)).fetchall()
    horario_raw = conn.execute(
        'SELECT dia, franja, num, materia, profesor FROM horarios_curso WHERE curso=? AND jornada=?',
        (alumno['curso'], alumno['jornada'])).fetchall()
    horario_map = {
        f"{r['dia']}_{r['franja']}": {'num': r['num'], 'materia': r['materia'], 'profesor': r['profesor']}
        for r in horario_raw}
    conn.close()
    return render_template('estudiante.html',
                           alumno=alumno, slug=slug, colegio=colegio, agenda=agenda,
                           notas_por_materia=notas_pm, evals_map=evals_map,
                           promedio_general=promedio_general,
                           asist_stats=asist_stats, historial_meses=historial_meses,
                           observaciones=observaciones, horario_map=horario_map)

# ── DIRECTORA ─────────────────────────────────────────────────────────────────
def get_directora(slug):
    did = session.get(f'directora_id_{slug}')
    if not did: return None
    conn = conectar(slug)
    d = conn.execute('SELECT * FROM directoras WHERE id=?', (did,)).fetchone()
    conn.close()
    return d

@app.route('/<slug>/directora/login', methods=['GET', 'POST'])
def directora_login(slug):
    require_colegio(slug)
    colegio = get_colegio(slug)
    error = exito = None
    if request.method == 'POST':
        u = request.form.get('usuario', '').strip()
        p = request.form.get('password', '').strip()
        conn = conectar(slug)
        d = conn.execute(
            'SELECT * FROM directoras WHERE usuario=? AND activo=1', (u,)).fetchone()
        conn.close()
        if d and verificar_pw(p, d['password']):
            session.permanent = True
            session[f'directora_id_{slug}'] = d['id']
            return redirect(url_for('directora_panel', slug=slug))
        error = 'Usuario o contraseña incorrectos.'
    return render_template('directora_login.html', slug=slug, colegio=colegio,
                           error=error, exito=exito)

@app.route('/<slug>/directora/registrar_directo', methods=['POST'])
def directora_registrar_directo(slug):
    require_colegio(slug)
    migrar_db(slug)
    colegio   = get_colegio(slug)
    error = exito = None
    nombre    = request.form.get('nombre', '').strip()
    usuario   = request.form.get('usuario', '').strip()
    pw        = request.form.get('password', '').strip()
    confirmar = request.form.get('confirmar_password', '').strip()
    curso     = request.form.get('curso', '').strip()
    jornada   = request.form.get('jornada', '').strip()
    email     = request.form.get('email', '').strip()
    pregunta  = request.form.get('pregunta_secreta', '').strip()
    respuesta = request.form.get('respuesta_secreta', '').strip().lower()
    codigo    = request.form.get('codigo_registro_dir', '').strip()

    # Validar código POR COLEGIO
    codigo_colegio = get_codigo_registro(slug)
    if codigo_colegio and codigo != codigo_colegio:
        error = 'Código de invitación incorrecto.'
    elif pw != confirmar:
        error = 'Las contraseñas no coinciden.'
    elif not nombre or not usuario or not pw or not curso or not jornada:
        error = 'Completa todos los campos obligatorios.'
    elif len(pw) < 6:
        error = 'Mínimo 6 caracteres.'
    elif not pregunta or not respuesta:
        error = 'Debes elegir una pregunta secreta y escribir tu respuesta.'
    else:
        conn = conectar(slug)
        if conn.execute('SELECT 1 FROM directoras WHERE usuario=?', (usuario,)).fetchone():
            error = 'Ese usuario ya existe. Elige otro nombre de usuario.'; conn.close()
        else:
            conn.execute(
                '''INSERT INTO directoras
                   (nombre,usuario,password,curso,jornada,email,pregunta_secreta,respuesta_secreta)
                   VALUES (?,?,?,?,?,?,?,?)''',
                (nombre, usuario, hash_pw(pw), curso, jornada, email, pregunta, respuesta))
            conn.commit(); conn.close()
            exito = '✅ Cuenta creada. Ya puedes ingresar.'
    return render_template('directora_login.html', slug=slug, colegio=colegio,
                           error=error, exito=exito)

@app.route('/<slug>/directora')
@app.route('/<slug>/directora/panel')
def directora_panel(slug):
    require_colegio(slug)
    directora = get_directora(slug)
    if not directora: return redirect(url_for('directora_login', slug=slug))
    colegio  = get_colegio(slug)
    curso    = directora['curso']
    jornada  = directora['jornada']
    periodo  = request.args.get('periodo', 1, type=int)
    num_periodos = int(colegio['num_periodos']) if colegio and colegio['num_periodos'] else 4
    conn = conectar(slug)
    alumnos = conn.execute(
        'SELECT * FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre COLLATE NOCASE',
        (curso, jornada)).fetchall()
    lista_materias = [r['materia'] for r in conn.execute(
        'SELECT DISTINCT materia FROM actividades WHERE curso=? AND jornada=? AND COALESCE(periodo,1)=? ORDER BY materia',
        (curso, jornada, periodo)).fetchall()]
    profs_raw = conn.execute(
        '''SELECT DISTINCT am.materia, p.nombre,
           (SELECT COUNT(*) FROM actividades a
            WHERE a.profesor_id=p.id AND a.curso=? AND a.jornada=?
            AND COALESCE(a.periodo,1)=?) as cnt
           FROM profesores p
           JOIN asignaciones_curso ac ON ac.profesor_id=p.id
           JOIN asignaciones_materia am ON am.profesor_id=p.id AND am.jornada=ac.jornada
           WHERE ac.curso=? AND ac.jornada=? AND p.activo=1''',
        (curso, jornada, periodo, curso, jornada)).fetchall()
    materias_enviadas = set()
    profesores = []
    for p in profs_raw:
        enviado = p['cnt'] > 0
        if enviado: materias_enviadas.add(p['materia'])
        profesores.append({'materia': p['materia'], 'nombre': p['nombre'],
                           'enviado': enviado, 'fecha_envio': None})
    tabla = []
    for a in alumnos:
        fila = {'id': a['id'], 'nombre': a['nombre'],
                'email': a['email_acudiente'] or '', 'materias': {}, 'promedio': None}
        todos_finales = []
        for mat in lista_materias:
            notas_r = conn.execute(
                '''SELECT n.val FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
                   WHERE n.aid=? AND ac.materia=? AND ac.curso=? AND ac.jornada=?
                   AND COALESCE(ac.periodo,1)=?''',
                (a['id'], mat, curso, jornada, periodo)).fetchall()
            ev = conn.execute(
                '''SELECT evaluacion, autoevaluacion FROM evaluaciones
                   WHERE aid=? AND materia=? AND jornada=? AND COALESCE(periodo,1)=?''',
                (a['id'], mat, jornada, periodo)).fetchone()
            act_prom = round(sum(r['val'] for r in notas_r) / len(notas_r), 2) if notas_r else None
            eval_v   = ev['evaluacion']     if ev and ev['evaluacion']     is not None else None
            auto_v   = ev['autoevaluacion'] if ev and ev['autoevaluacion'] is not None else None
            if act_prom is not None or eval_v is not None or auto_v is not None:
                total_peso = 0; nota_final = 0
                if act_prom is not None: nota_final += act_prom * 0.65; total_peso += 0.65
                if eval_v   is not None: nota_final += eval_v   * 0.25; total_peso += 0.25
                if auto_v   is not None: nota_final += auto_v   * 0.10; total_peso += 0.10
                final = round(nota_final / total_peso, 2) if total_peso else None
            else:
                final = None
            fila['materias'][mat] = {'act': act_prom, 'eval': eval_v, 'auto': auto_v, 'final': final}
            if final is not None: todos_finales.append(final)
        fila['promedio'] = round(sum(todos_finales) / len(todos_finales), 2) if todos_finales else None
        tabla.append(fila)
    conn.close()
    return render_template('directora_panel.html',
                           slug=slug, colegio=colegio, directora=directora,
                           curso=curso, jornada=jornada, periodo=periodo,
                           num_periodos=num_periodos,
                           lista_materias=lista_materias,
                           materias_enviadas=materias_enviadas,
                           profesores=profesores, tabla=tabla)

@app.route('/<slug>/directora/boletin_pdf')
def directora_boletin_pdf(slug):
    require_colegio(slug)
    directora = get_directora(slug)
    if not directora: return redirect(url_for('directora_login', slug=slug))
    from flask import Response
    colegio  = get_colegio(slug)
    curso    = directora['curso']
    jornada  = directora['jornada']
    periodo  = request.args.get('periodo', 1, type=int)
    aid_solo = request.args.get('aid', type=int)
    conn = conectar(slug)
    if aid_solo:
        alumnos = conn.execute(
            'SELECT * FROM alumnos WHERE id=? AND curso=?', (aid_solo, curso)).fetchall()
    else:
        alumnos = conn.execute(
            'SELECT * FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre COLLATE NOCASE',
            (curso, jornada)).fetchall()
    all_pdfs = []
    for alumno in alumnos:
        pdf_bytes, _ = generar_pdf_alumno(alumno, slug, colegio, curso, jornada, periodo, conn)
        all_pdfs.append(pdf_bytes)
    conn.close()
    if not all_pdfs: return ('Sin alumnos', 404)
    if len(all_pdfs) == 1:
        return Response(all_pdfs[0], mimetype='application/pdf',
                        headers={'Content-Disposition':
                                 f'attachment;filename=boletin_{curso}_{jornada}_P{periodo}.pdf'})
    try:
        from pypdf import PdfWriter, PdfReader
        writer = PdfWriter()
        for pdf_bytes in all_pdfs:
            reader = PdfReader(BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)
        out = BytesIO()
        writer.write(out); out.seek(0)
        return Response(out, mimetype='application/pdf',
                        headers={'Content-Disposition':
                                 f'attachment;filename=boletin_{curso}_{jornada}_P{periodo}.pdf'})
    except ImportError:
        return Response(all_pdfs[0], mimetype='application/pdf',
                        headers={'Content-Disposition':
                                 f'attachment;filename=boletin_{curso}_{jornada}_P{periodo}.pdf'})

@app.route('/<slug>/directora/logout')
def directora_logout(slug):
    session.pop(f'directora_id_{slug}', None)
    return redirect(url_for('directora_login', slug=slug))

@app.route('/<slug>/directora/enviar_correos', methods=['POST'])
def directora_enviar_correos(slug):
    require_colegio(slug)
    directora = get_directora(slug)
    if not directora: return jsonify({'ok': False, 'mensaje': 'No autorizado'})
    if not validar_csrf(): return jsonify({'ok': False, 'mensaje': 'Error CSRF'})
    import base64
    colegio  = get_colegio(slug)
    curso    = directora['curso']
    jornada  = directora['jornada']
    periodo  = int(request.form.get('periodo', 1))
    aid_solo = request.form.get('aid', type=int)
    conn     = conectar(slug)
    if aid_solo:
        alumnos = conn.execute(
            'SELECT * FROM alumnos WHERE id=? AND curso=?', (aid_solo, curso)).fetchall()
    else:
        alumnos = conn.execute(
            'SELECT * FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre COLLATE NOCASE',
            (curso, jornada)).fetchall()
    enviados = fallidos = sin_correo = 0
    for alumno in alumnos:
        email_dest = alumno['email_acudiente'] if alumno['email_acudiente'] else None
        if not email_dest: sin_correo += 1; continue
        try:
            pdf_bytes, prom_general = generar_pdf_alumno(
                alumno, slug, colegio, curso, jornada, periodo, conn)
        except Exception as e:
            logger.error(f'Error generando PDF para {alumno["nombre"]}: {e}')
            fallidos += 1; continue
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
            sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
            mensaje = Mail(
                from_email=EMAIL_ORIGEN,
                to_emails=email_dest,
                subject=f'Boletín de Notas — {alumno["nombre"]} · Periodo {periodo}',
                html_content=f'''<div style="font-family:sans-serif;max-width:500px;margin:0 auto;">
                    <h2 style="color:#6c63ff;">LUMINI — Boletín de Notas</h2>
                    <p>Estimado acudiente,</p>
                    <p>Adjunto encontrará el boletín de notas de <strong>{alumno["nombre"]}</strong>
                       correspondiente al <strong>Periodo {periodo}</strong>.</p>
                    <p><strong>Promedio general: {prom_general}</strong></p>
                    <p style="color:#888;font-size:12px;">
                       {colegio["nombre"] if colegio else slug} · {curso} · {jornada}</p>
                </div>'''
            )
            adjunto = Attachment(
                FileContent(base64.b64encode(pdf_bytes).decode()),
                FileName(f'boletin_{alumno["nombre"].replace(" ", "_")}_P{periodo}.pdf'),
                FileType('application/pdf'),
                Disposition('attachment'))
            mensaje.attachment = adjunto
            sg.client.mail.send.post(request_body=mensaje.get())
            enviados += 1
            logger.info(f'Boletín enviado a {email_dest} para {alumno["nombre"]}')
        except Exception as e:
            logger.error(f'Error correo {email_dest}: {e}')
            fallidos += 1
    conn.close()
    partes = []
    if enviados:   partes.append(f'✅ {enviados} enviado(s)')
    if fallidos:   partes.append(f'❌ {fallidos} fallido(s)')
    if sin_correo: partes.append(f'⚠️ {sin_correo} sin correo registrado')
    return jsonify({'ok': fallidos == 0, 'mensaje': ' · '.join(partes) or 'Sin destinatarios'})

@app.route('/<slug>/directora/guardar_email', methods=['POST'])
def directora_guardar_email(slug):
    require_colegio(slug)
    directora = get_directora(slug)
    if not directora: return ('', 403)
    if not validar_csrf(): return ('Error CSRF', 403)
    aid   = request.form.get('aid', type=int)
    email = request.form.get('email', '').strip()
    conn  = conectar(slug)
    conn.execute('UPDATE alumnos SET email_acudiente=? WHERE id=?', (email, aid))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/<slug>/directora/crear_desde_panel', methods=['POST'])
def directora_crear_desde_panel(slug):
    require_colegio(slug)
    directora = get_directora(slug)
    if not directora: return jsonify({'ok': False, 'mensaje': 'No autorizado'})
    if not validar_csrf(): return jsonify({'ok': False, 'mensaje': 'Error CSRF'})
    migrar_db(slug)
    nombre  = request.form.get('nombre', '').strip()
    usuario = request.form.get('usuario', '').strip()
    pw      = request.form.get('password', '').strip()
    curso   = request.form.get('curso', '').strip()
    email   = request.form.get('email', '').strip()
    jornada = directora['jornada']
    if not nombre or not usuario or not pw or not curso:
        return jsonify({'ok': False, 'mensaje': 'Completa todos los campos.'})
    if len(pw) < 6:
        return jsonify({'ok': False, 'mensaje': 'Mínimo 6 caracteres.'})
    conn = conectar(slug)
    if conn.execute('SELECT 1 FROM directoras WHERE usuario=?', (usuario,)).fetchone():
        conn.close()
        return jsonify({'ok': False, 'mensaje': 'Ese usuario ya existe.'})
    conn.execute(
        'INSERT INTO directoras (nombre,usuario,password,curso,jornada,email) VALUES (?,?,?,?,?,?)',
        (nombre, usuario, hash_pw(pw), curso, jornada, email))
    conn.commit(); conn.close()
    return jsonify({'ok': True, 'mensaje': f'Cuenta creada para {nombre}.'})

# ── STATIC / ROOT / ERRORS ────────────────────────────────────────────────────
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), 'static'), filename)

@app.route("/")
def index():
    conn = conectar_master()
    colegios = conn.execute("SELECT slug, nombre, logo FROM colegios WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template("index_root.html", colegios=colegios)
    colegios = conn.execute("SELECT slug, nombre, logo FROM colegios WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template("index_root.html", colegios=colegios)

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', codigo=404, mensaje='Página no encontrada.'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', codigo=403, mensaje='Este colegio está inactivo.'), 403

@app.errorhandler(413)
def too_large(e):
    return render_template('error.html', codigo=413,
                           mensaje='El archivo es demasiado grande. Máximo permitido: 2 MB.'), 413

# ── FILTRO DÍAS RESTANTES ─────────────────────────────────────────────────────
from datetime import date as _date

@app.template_filter('dias_restantes')
def dias_restantes(fecha_str):
    try:
        fecha = _date.fromisoformat(str(fecha_str))
        return (fecha - _date.today()).days
    except:
        return None

# ── API PROFESORES PARA ADMIN ─────────────────────────────────────────────────
@app.route('/admin/profesores/<slug>')
def admin_ver_profesores(slug):
    if not session.get('admin_auth'):
        return jsonify({'error': 'No autorizado'}), 403
    conn = conectar(slug)
    profs = conn.execute(
        'SELECT id, nombre, usuario, activo FROM profesores ORDER BY nombre').fetchall()
    resultado = []
    for p in profs:
        mats = conn.execute(
            'SELECT materia, jornada FROM asignaciones_materia WHERE profesor_id=? ORDER BY jornada, materia',
            (p['id'],)).fetchall()
        resultado.append({
            'nombre': p['nombre'], 'usuario': p['usuario'], 'activo': p['activo'],
            'materias': [{'materia': m['materia'], 'jornada': m['jornada']} for m in mats]
        })
    conn.close()
    return jsonify({'profesores': resultado})

# ── BACKUP AUTOMÁTICO ─────────────────────────────────────────────────────────
import threading, shutil
from datetime import datetime as _dt

def hacer_backup():
    try:
        hoy = _dt.now().strftime('%Y-%m-%d')
        backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(MASTER_DB, os.path.join(backup_dir, f'master_{hoy}.db'))
        for f in os.listdir(DB_FOLDER):
            if f.endswith('.db'):
                shutil.copy2(os.path.join(DB_FOLDER, f),
                             os.path.join(backup_dir, f'{f[:-3]}_{hoy}.db'))
        logger.info(f'Backup automático completado: {hoy}')
    except Exception as e:
        logger.error(f'Error en backup: {e}')

def programar_backup():
    hacer_backup()
    t = threading.Timer(86400, programar_backup)
    t.daemon = True
    t.start()

init_master_db()
threading.Timer(30, programar_backup).start()