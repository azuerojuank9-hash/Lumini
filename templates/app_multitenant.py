from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, Response, abort, g
import sqlite3, hashlib, os, io, time, secrets
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

app = Flask(__name__)
app.secret_key = 'lumini2026xK9mP2qL8nRvT5wYjBdZeA'

# ── CONFIGURACIÓN MULTI-TENANT ────────────────────────────────────────────────
# Carpeta donde se guardan las bases de datos de cada colegio
DB_FOLDER = os.path.join(os.path.dirname(__file__), 'colegios_db')
os.makedirs(DB_FOLDER, exist_ok=True)

# Base de datos maestra (gestiona los colegios registrados)
MASTER_DB = os.path.join(os.path.dirname(__file__), 'master.db')

# Contraseña del panel admin (cámbiala y ponla en variable de entorno)
ADMIN_PASSWORD = 'azuerojuank9'

MATERIAS = [
    'Artes', 'Matemáticas', 'Cipol y Econ', 'Física', 'Química',
    'Español', 'Inglés', 'Biología', 'Sociales',
    'Tecnología e Informática', 'Filosofía', 'Educación Física'
]

# ── PROTECCIÓN CSRF ───────────────────────────────────────────────────────────
def generar_csrf():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

def validar_csrf():
    token_form    = request.form.get('_csrf_token', '')
    token_session = session.get('_csrf_token', '')
    return bool(token_form and token_form == token_session)

app.jinja_env.globals['csrf_token'] = generar_csrf

# ── PROTECCIÓN FUERZA BRUTA ───────────────────────────────────────────────────
login_intentos = {}
MAX_INTENTOS   = 5
BLOQUEO_SEG    = 5 * 60

def ip_bloqueada(ip):
    dato = login_intentos.get(ip)
    if not dato: return False
    if dato['bloqueado_hasta'] and time.time() < dato['bloqueado_hasta']:
        return int(dato['bloqueado_hasta'] - time.time())
    return False

def registrar_intento_fallido(ip):
    dato = login_intentos.setdefault(ip, {'intentos': 0, 'bloqueado_hasta': None})
    dato['intentos'] += 1
    if dato['intentos'] >= MAX_INTENTOS:
        dato['bloqueado_hasta'] = time.time() + BLOQUEO_SEG
    return dato['intentos']

def limpiar_intentos(ip):
    login_intentos.pop(ip, None)

# ── HASH SEGURO ───────────────────────────────────────────────────────────────
def hash_pw(pw, sal=None):
    if sal is None:
        sal = secrets.token_hex(16)
    digest = hashlib.sha256((sal + pw).encode()).hexdigest()
    return f"{sal}${digest}"

def verificar_pw(pw_plano, pw_almacenada):
    if not pw_almacenada: return False
    if '$' in pw_almacenada:
        sal, _ = pw_almacenada.split('$', 1)
        return hash_pw(pw_plano, sal) == pw_almacenada
    return hashlib.sha256(pw_plano.encode()).hexdigest() == pw_almacenada

# ── BASE DE DATOS MAESTRA ─────────────────────────────────────────────────────
def conectar_master():
    conn = sqlite3.connect(MASTER_DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_master_db():
    conn = conectar_master()
    conn.execute('''CREATE TABLE IF NOT EXISTS colegios (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        slug       TEXT UNIQUE NOT NULL,
        nombre     TEXT NOT NULL,
        activo     INTEGER DEFAULT 1,
        creado     TEXT DEFAULT (date('now'))
    )''')
    conn.commit()
    conn.close()

def get_colegio(slug):
    conn = conectar_master()
    c = conn.execute('SELECT * FROM colegios WHERE slug=?', (slug,)).fetchone()
    conn.close()
    return c

def colegio_activo(slug):
    c = get_colegio(slug)
    return c and c['activo'] == 1

# ── BASE DE DATOS POR COLEGIO ─────────────────────────────────────────────────
def db_path(slug):
    return os.path.join(DB_FOLDER, f'{slug}.db')

def conectar(slug):
    conn = sqlite3.connect(db_path(slug))
    conn.row_factory = sqlite3.Row
    return conn

def init_db(slug):
    conn = conectar(slug)
    conn.execute('''CREATE TABLE IF NOT EXISTS profesores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL, usuario TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL, materia TEXT NOT NULL, aprobado INTEGER DEFAULT 1
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS asignaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profesor_id INTEGER NOT NULL, curso TEXT NOT NULL,
        UNIQUE(profesor_id, curso)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS alumnos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL, curso TEXT NOT NULL, num_curso INTEGER DEFAULT 0
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS asistencia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aid INTEGER, fecha TEXT, estado TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS compromisos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT, fecha TEXT, materia TEXT, curso TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS observaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aid INTEGER, materia TEXT, texto TEXT, fecha TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS actividades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profesor_id INTEGER NOT NULL, materia TEXT NOT NULL,
        curso TEXT NOT NULL, nombre TEXT NOT NULL, orden INTEGER DEFAULT 0
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS notas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aid INTEGER NOT NULL, actividad_id INTEGER NOT NULL, val REAL NOT NULL,
        UNIQUE(aid, actividad_id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS evaluaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aid INTEGER NOT NULL, profesor_id INTEGER NOT NULL,
        materia TEXT NOT NULL, evaluacion REAL, autoevaluacion REAL,
        UNIQUE(aid, profesor_id)
    )''')
    conn.commit()
    conn.close()

# ── HELPERS ───────────────────────────────────────────────────────────────────
def get_profesor(slug):
    pid = session.get(f'profesor_id_{slug}')
    if not pid: return None
    conn = conectar(slug)
    p = conn.execute('SELECT * FROM profesores WHERE id=?', (pid,)).fetchone()
    conn.close()
    return p

def get_cursos_profesor(slug, pid):
    conn = conectar(slug)
    rows = conn.execute('SELECT curso FROM asignaciones WHERE profesor_id=? ORDER BY curso', (pid,)).fetchall()
    conn.close()
    return [r['curso'] for r in rows]

def require_colegio(slug):
    """Verifica que el colegio exista y esté activo. Aborta con 404/403 si no."""
    if not get_colegio(slug):
        abort(404)
    if not colegio_activo(slug):
        abort(403)

# ── MIDDLEWARE: slug en todas las rutas de colegio ────────────────────────────
# Todas las rutas de colegio usan el prefijo /<slug>/

# ── ADMIN PANEL ───────────────────────────────────────────────────────────────

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    error = exito = None
    if not session.get('admin_auth'):
        if request.method == 'POST' and request.form.get('accion') == 'admin_login':
            pw = request.form.get('password', '')
            if pw == ADMIN_PASSWORD:
                session['admin_auth'] = True
                return redirect(url_for('admin'))
            else:
                error = 'Contraseña incorrecta.'
        return render_template('admin_login.html', error=error)

    conn = conectar_master()
    colegios = conn.execute('SELECT * FROM colegios ORDER BY creado DESC').fetchall()
    conn.close()

    if request.method == 'POST':
        accion = request.form.get('accion')

        if accion == 'crear_colegio':
            nombre = request.form.get('nombre', '').strip()
            slug   = request.form.get('slug', '').strip().lower().replace(' ', '-')
            if not nombre or not slug:
                error = 'Nombre y slug son obligatorios.'
            elif not slug.replace('-', '').isalnum():
                error = 'El slug solo puede tener letras, números y guiones.'
            else:
                try:
                    cm = conectar_master()
                    cm.execute('INSERT INTO colegios (slug, nombre) VALUES (?,?)', (slug, nombre))
                    cm.commit(); cm.close()
                    init_db(slug)
                    exito = f'Colegio "{nombre}" creado. URL: /{slug}/login'
                except sqlite3.IntegrityError:
                    error = f'El slug "{slug}" ya existe.'

        elif accion == 'toggle_colegio':
            slug_t = request.form.get('slug')
            cm = conectar_master()
            actual = cm.execute('SELECT activo FROM colegios WHERE slug=?', (slug_t,)).fetchone()
            if actual:
                nuevo = 0 if actual['activo'] else 1
                cm.execute('UPDATE colegios SET activo=? WHERE slug=?', (nuevo, slug_t))
                cm.commit()
            cm.close()
            return redirect(url_for('admin'))

        elif accion == 'eliminar_colegio':
            slug_e = request.form.get('slug')
            cm = conectar_master()
            cm.execute('DELETE FROM colegios WHERE slug=?', (slug_e,))
            cm.commit(); cm.close()
            db = db_path(slug_e)
            if os.path.exists(db):
                os.rename(db, db + '.bak')
            exito = f'Colegio "{slug_e}" eliminado (DB guardada como backup).'

        conn = conectar_master()
        colegios = conn.execute('SELECT * FROM colegios ORDER BY creado DESC').fetchall()
        conn.close()

    return render_template('admin_panel.html', colegios=colegios, error=error, exito=exito)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_auth', None)
    return redirect(url_for('admin'))

# ── LOGIN POR COLEGIO ─────────────────────────────────────────────────────────

@app.route('/<slug>/login', methods=['GET', 'POST'])
def login(slug):
    require_colegio(slug)
    init_master_db()
    colegio = get_colegio(slug)
    error = None
    ip = request.remote_addr

    if request.method == 'POST':
        if not validar_csrf():
            error = 'Error de seguridad. Recarga la página.'
            return render_template('login.html', error=error, materias=MATERIAS, slug=slug, colegio=colegio)

        accion = request.form.get('accion')

        if accion == 'profesor_login':
            bloqueado = ip_bloqueada(ip)
            if bloqueado:
                error = f'Demasiados intentos. Espera {bloqueado} segundos.'
                return render_template('login.html', error=error, materias=MATERIAS, slug=slug, colegio=colegio)

            u = request.form.get('usuario', '').strip()
            p = request.form.get('password', '').strip()
            if not p:
                error = 'La contraseña es obligatoria.'
            else:
                conn = conectar(slug)
                prof = conn.execute('SELECT * FROM profesores WHERE usuario=?', (u,)).fetchone()
                if prof:
                    if '$' not in prof['password']:
                        viejo = hashlib.sha256(p.encode()).hexdigest()
                        if viejo == prof['password']:
                            conn.execute('UPDATE profesores SET password=? WHERE id=?', (hash_pw(p), prof['id']))
                            conn.commit()
                            session[f'rol_{slug}'] = 'profesor'
                            session[f'profesor_id_{slug}'] = prof['id']
                            limpiar_intentos(ip)
                            conn.close()
                            return redirect(url_for('home', slug=slug))
                        else:
                            conn.close()
                            registrar_intento_fallido(ip)
                            error = 'Contraseña incorrecta.'
                    elif verificar_pw(p, prof['password']):
                        session[f'rol_{slug}'] = 'profesor'
                        session[f'profesor_id_{slug}'] = prof['id']
                        limpiar_intentos(ip)
                        conn.close()
                        return redirect(url_for('home', slug=slug))
                    else:
                        conn.close()
                        intentos = registrar_intento_fallido(ip)
                        restantes = MAX_INTENTOS - intentos
                        error = f'Contraseña incorrecta. Te quedan {restantes} intentos.' if restantes > 0 else f'Bloqueado {BLOQUEO_SEG//60} min.'
                else:
                    conn.close()
                    registrar_intento_fallido(ip)
                    error = 'Usuario no encontrado.'

        elif accion == 'profesor_registro':
            nombre  = request.form.get('nombre', '').strip()
            usuario = request.form.get('reg_usuario', '').strip()
            pw      = request.form.get('reg_password', '').strip()
            materia = request.form.get('materia', '').strip()
            cursos  = request.form.getlist('cursos')
            extra   = request.form.get('cursos_extra', '').strip()
            if extra:
                cursos += [c.strip() for c in extra.split(',') if c.strip()]
            if not nombre or not usuario or not materia:
                error = 'Completa nombre, usuario y materia.'
            elif not pw:
                error = 'La contraseña es obligatoria.'
            elif len(pw) < 6:
                error = 'Mínimo 6 caracteres.'
            else:
                conn = conectar(slug)
                existe = conn.execute('SELECT 1 FROM profesores WHERE usuario=?', (usuario,)).fetchone()
                if existe:
                    error = 'Ese usuario ya existe.'
                else:
                    cur = conn.execute(
                        'INSERT INTO profesores (nombre,usuario,password,materia,aprobado) VALUES (?,?,?,?,1)',
                        (nombre, usuario, hash_pw(pw), materia)
                    )
                    pid = cur.lastrowid
                    for c in cursos:
                        if c:
                            conn.execute('INSERT OR IGNORE INTO asignaciones (profesor_id,curso) VALUES (?,?)', (pid, c))
                    conn.commit(); conn.close()
                    error = '✅ Registro exitoso. Ya puedes ingresar.'

        elif accion == 'estudiante':
            nombre = request.form.get('nombre_est', '').strip().lower()
            conn = conectar(slug)
            alumno = conn.execute('SELECT * FROM alumnos WHERE LOWER(nombre)=?', (nombre,)).fetchone()
            conn.close()
            if alumno:
                session[f'rol_{slug}'] = 'estudiante'
                session[f'alumno_id_{slug}'] = alumno['id']
                return redirect(url_for('vista_estudiante', slug=slug))
            error = 'No se encontró ese estudiante.'

    return render_template('login.html', error=error, materias=MATERIAS, slug=slug, colegio=colegio)

@app.route('/<slug>/logout')
def logout(slug):
    session.pop(f'rol_{slug}', None)
    session.pop(f'profesor_id_{slug}', None)
    session.pop(f'alumno_id_{slug}', None)
    return redirect(url_for('login', slug=slug))

# ── HOME PROFESOR ─────────────────────────────────────────────────────────────

@app.route('/<slug>/')
@app.route('/<slug>')
def home(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    colegio = get_colegio(slug)

    mis_cursos = get_cursos_profesor(slug, prof['id'])
    curso_sel  = request.args.get('curso', mis_cursos[0] if mis_cursos else None)

    conn = conectar(slug)
    alumnos = actividades = agenda = []

    if curso_sel and curso_sel in mis_cursos:
        alumnos = conn.execute('SELECT * FROM alumnos WHERE curso=? ORDER BY num_curso', (curso_sel,)).fetchall()
        actividades = conn.execute(
            'SELECT * FROM actividades WHERE profesor_id=? AND curso=? ORDER BY orden',
            (prof['id'], curso_sel)
        ).fetchall()
        agenda = conn.execute(
            'SELECT * FROM compromisos WHERE materia=? AND curso=? ORDER BY fecha',
            (prof['materia'], curso_sel)
        ).fetchall()

    MESES = {'01':'Enero','02':'Febrero','03':'Marzo','04':'Abril','05':'Mayo','06':'Junio',
             '07':'Julio','08':'Agosto','09':'Septiembre','10':'Octubre','11':'Noviembre','12':'Diciembre'}

    datos = []
    suma_prom = 0
    for a in alumnos:
        notas_raw = conn.execute(
            '''SELECT n.actividad_id, n.val, n.id FROM notas n
               JOIN actividades ac ON ac.id=n.actividad_id
               WHERE n.aid=? AND ac.profesor_id=? AND ac.curso=?''',
            (a['id'], prof['id'], curso_sel)
        ).fetchall()
        notas_map = {nr['actividad_id']: {'val': nr['val'], 'id': nr['id']} for nr in notas_raw}
        vals = [nr['val'] for nr in notas_raw]
        prom = sum(vals)/len(vals) if vals else 0
        ev = conn.execute(
            'SELECT evaluacion, autoevaluacion FROM evaluaciones WHERE aid=? AND profesor_id=?',
            (a['id'], prof['id'])
        ).fetchone()
        historial_raw = conn.execute('SELECT fecha, estado FROM asistencia WHERE aid=? ORDER BY fecha', (a['id'],)).fetchall()
        hist_meses = {}
        for h in historial_raw:
            if h['fecha']:
                p2 = h['fecha'].split('-')
                if len(p2) >= 2:
                    label = f"{MESES.get(p2[1],p2[1])} {p2[0]}"
                    hist_meses.setdefault(label,[]).append({'fecha':h['fecha'],'estado':h['estado']})
        asis = conn.execute('SELECT estado FROM asistencia WHERE aid=? ORDER BY id DESC LIMIT 1',(a['id'],)).fetchone()
        obs  = conn.execute('SELECT id,materia,texto,fecha FROM observaciones WHERE aid=? ORDER BY fecha DESC',(a['id'],)).fetchall()
        suma_prom += prom
        datos.append({
            'id': a['id'], 'num_curso': a['num_curso'],
            'nombre': a['nombre'], 'curso': a['curso'],
            'promedio': round(prom,2), 'notas_map': notas_map,
            'evaluacion':     ev['evaluacion']     if ev and ev['evaluacion']     is not None else '',
            'autoevaluacion': ev['autoevaluacion'] if ev and ev['autoevaluacion'] is not None else '',
            'asistencia': asis['estado'] if asis else '-',
            'historial_meses': hist_meses,
            'observaciones': [dict(o) for o in obs],
        })

    prom_gral = round(suma_prom/len(datos),2) if datos else 0
    mejor = max(datos, key=lambda x: x['promedio'], default={'nombre':'N/A','promedio':0})
    conn.close()

    return render_template('index.html',
        profesor=prof, mis_cursos=mis_cursos, curso_sel=curso_sel,
        estudiantes=datos, actividades=actividades, compromisos=agenda,
        prom_general=prom_gral, mejor=mejor, slug=slug, colegio=colegio)

# ── ACTIVIDADES ───────────────────────────────────────────────────────────────

@app.route('/<slug>/nueva_actividad', methods=['POST'])
def nueva_actividad(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    if not validar_csrf(): return ('Error CSRF', 403)
    nombre    = request.form.get('nombre','').strip()
    curso_sel = request.form.get('curso_sel','')
    if nombre and curso_sel:
        conn = conectar(slug)
        max_ord = conn.execute(
            'SELECT COALESCE(MAX(orden),0) FROM actividades WHERE profesor_id=? AND curso=?',
            (prof['id'], curso_sel)
        ).fetchone()[0]
        conn.execute('INSERT INTO actividades (profesor_id,materia,curso,nombre,orden) VALUES (?,?,?,?,?)',
                     (prof['id'], prof['materia'], curso_sel, nombre, max_ord+1))
        conn.commit(); conn.close()
    return redirect(url_for('home', slug=slug, curso=curso_sel))

@app.route('/<slug>/borrar_actividad/<int:act_id>')
def borrar_actividad(slug, act_id):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    conn = conectar(slug)
    act = conn.execute('SELECT profesor_id, curso FROM actividades WHERE id=?',(act_id,)).fetchone()
    if act and act['profesor_id'] == prof['id']:
        conn.execute('DELETE FROM notas WHERE actividad_id=?',(act_id,))
        conn.execute('DELETE FROM actividades WHERE id=?',(act_id,))
        conn.commit()
        curso = act['curso']
    else:
        curso = ''
    conn.close()
    return redirect(url_for('home', slug=slug, curso=curso))

# ── NOTAS ─────────────────────────────────────────────────────────────────────

@app.route('/<slug>/guardar_nota', methods=['POST'])
def guardar_nota(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return ('',403)
    aid = request.form.get('aid', type=int)
    actividad_id = request.form.get('actividad_id', type=int)
    val = request.form.get('val', type=float)
    if None in (aid, actividad_id, val): return ('',400)
    conn = conectar(slug)
    act = conn.execute('SELECT profesor_id FROM actividades WHERE id=?',(actividad_id,)).fetchone()
    if act and act['profesor_id'] == prof['id']:
        conn.execute('''INSERT INTO notas (aid,actividad_id,val) VALUES (?,?,?)
                        ON CONFLICT(aid,actividad_id) DO UPDATE SET val=excluded.val''',
                     (aid, actividad_id, val))
        conn.commit()
    conn.close()
    return ('',204)

@app.route('/<slug>/borrar_nota_celda/<int:aid>/<int:act_id>')
def borrar_nota_celda(slug, aid, act_id):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    conn = conectar(slug)
    act = conn.execute('SELECT profesor_id, curso FROM actividades WHERE id=?',(act_id,)).fetchone()
    if act and act['profesor_id'] == prof['id']:
        conn.execute('DELETE FROM notas WHERE aid=? AND actividad_id=?',(aid,act_id))
        conn.commit()
        curso = act['curso']
    else:
        curso = ''
    conn.close()
    return redirect(url_for('home', slug=slug, curso=curso))

# ── EVALUACIONES ──────────────────────────────────────────────────────────────

@app.route('/<slug>/guardar_evaluacion', methods=['POST'])
def guardar_evaluacion(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return ('',403)
    aid = request.form.get('aid', type=int)
    evaluacion = request.form.get('evaluacion', type=float)
    autoevaluacion = request.form.get('autoevaluacion', type=float)
    if aid is None: return ('',400)
    conn = conectar(slug)
    conn.execute('''INSERT INTO evaluaciones (aid,profesor_id,materia,evaluacion,autoevaluacion)
                    VALUES (?,?,?,?,?)
                    ON CONFLICT(aid,profesor_id) DO UPDATE SET
                        evaluacion=COALESCE(excluded.evaluacion,evaluacion),
                        autoevaluacion=COALESCE(excluded.autoevaluacion,autoevaluacion)''',
                 (aid, prof['id'], prof['materia'], evaluacion, autoevaluacion))
    conn.commit(); conn.close()
    return ('',204)

# ── AGENDA ────────────────────────────────────────────────────────────────────

@app.route('/<slug>/nuevo_trabajo', methods=['POST'])
def nuevo_trabajo(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    if not validar_csrf(): return ('Error CSRF', 403)
    curso_sel = request.form.get('curso_sel','')
    conn = conectar(slug)
    conn.execute('INSERT INTO compromisos (titulo,fecha,materia,curso) VALUES (?,?,?,?)',
                 (request.form.get('titulo'), request.form.get('fecha'), prof['materia'], curso_sel))
    conn.commit(); conn.close()
    return redirect(url_for('home', slug=slug, curso=curso_sel))

@app.route('/<slug>/borrar_trabajo/<int:id_t>')
def borrar_trabajo(slug, id_t):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    conn = conectar(slug)
    c = conn.execute('SELECT curso FROM compromisos WHERE id=?',(id_t,)).fetchone()
    curso = c['curso'] if c else ''
    conn.execute('DELETE FROM compromisos WHERE id=? AND materia=?',(id_t, prof['materia']))
    conn.commit(); conn.close()
    return redirect(url_for('home', slug=slug, curso=curso))

@app.route('/<slug>/borrar_trabajo_estudiante/<int:id_t>')
def borrar_trabajo_estudiante(slug, id_t):
    require_colegio(slug)
    if session.get(f'rol_{slug}') != 'estudiante': return redirect(url_for('login', slug=slug))
    conn = conectar(slug)
    conn.execute('DELETE FROM compromisos WHERE id=?',(id_t,))
    conn.commit(); conn.close()
    return redirect(url_for('vista_estudiante', slug=slug))

# ── ALUMNOS ───────────────────────────────────────────────────────────────────

@app.route('/<slug>/registrar', methods=['POST'])
def registrar(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    if not validar_csrf(): return ('Error CSRF', 403)
    nom       = request.form.get('nombre','').strip()
    cur       = request.form.get('curso','').strip()
    curso_sel = request.form.get('curso_sel', cur)
    conn = conectar(slug)
    ids = [r['num_curso'] for r in conn.execute('SELECT num_curso FROM alumnos WHERE curso=?',(cur,)).fetchall()]
    nuevo_num = next((i for i in range(1,501) if i not in ids), None)
    if nuevo_num:
        conn.execute('INSERT INTO alumnos (nombre,curso,num_curso) VALUES (?,?,?)',(nom,cur,nuevo_num))
        conn.commit()
    conn.close()
    return redirect(url_for('home', slug=slug, curso=curso_sel))

@app.route('/<slug>/borrar_alumno/<int:id>')
def borrar_alumno(slug, id):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    curso_sel = request.args.get('curso','')
    conn = conectar(slug)
    conn.execute('DELETE FROM alumnos WHERE id=?',(id,))
    conn.execute('DELETE FROM notas WHERE aid=?',(id,))
    conn.execute('DELETE FROM evaluaciones WHERE aid=? AND profesor_id=?',(id, prof['id']))
    conn.commit(); conn.close()
    return redirect(url_for('home', slug=slug, curso=curso_sel))

# ── ASISTENCIA ────────────────────────────────────────────────────────────────

@app.route('/<slug>/marcar_asistencia', methods=['POST'])
def marcar_asistencia(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    curso_sel = request.form.get('curso_sel','')
    conn = conectar(slug)
    conn.execute('INSERT INTO asistencia (aid,fecha,estado) VALUES (?,date("now"),?)',
                 (request.form.get('aid'), request.form.get('estado')))
    conn.commit(); conn.close()
    return redirect(url_for('home', slug=slug, curso=curso_sel))

# ── OBSERVACIONES ─────────────────────────────────────────────────────────────

@app.route('/<slug>/agregar_observacion', methods=['POST'])
def agregar_observacion(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    curso_sel = request.form.get('curso_sel','')
    texto = request.form.get('texto','').strip()
    if texto:
        conn = conectar(slug)
        conn.execute('INSERT INTO observaciones (aid,materia,texto,fecha) VALUES (?,?,?,date("now"))',
                     (request.form.get('aid'), prof['materia'], texto))
        conn.commit(); conn.close()
    return redirect(url_for('home', slug=slug, curso=curso_sel))

@app.route('/<slug>/borrar_observacion/<int:id_o>')
def borrar_observacion(slug, id_o):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    curso_sel = request.args.get('curso','')
    conn = conectar(slug)
    obs = conn.execute('SELECT materia FROM observaciones WHERE id=?',(id_o,)).fetchone()
    if obs and obs['materia'] == prof['materia']:
        conn.execute('DELETE FROM observaciones WHERE id=?',(id_o,))
        conn.commit()
    conn.close()
    return redirect(url_for('home', slug=slug, curso=curso_sel))

# ── PERFIL ────────────────────────────────────────────────────────────────────

@app.route('/<slug>/cambiar_password', methods=['GET','POST'])
def cambiar_password(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    error = exito = None
    if request.method == 'POST':
        if not validar_csrf():
            error = 'Error de seguridad.'
        else:
            actual    = request.form.get('actual','').strip()
            nueva     = request.form.get('nueva','').strip()
            confirmar = request.form.get('confirmar','').strip()
            if not verificar_pw(actual, prof['password']):
                error = 'Contraseña actual incorrecta.'
            elif len(nueva) < 6:
                error = 'Mínimo 6 caracteres.'
            elif nueva != confirmar:
                error = 'Las contraseñas no coinciden.'
            else:
                conn = conectar(slug)
                conn.execute('UPDATE profesores SET password=? WHERE id=?',(hash_pw(nueva), prof['id']))
                conn.commit(); conn.close()
                exito = '¡Contraseña cambiada!'
    mis_cursos = get_cursos_profesor(slug, prof['id'])
    return render_template('cambiar_password.html', profesor=prof, mis_cursos=mis_cursos,
                           error=error, exito=exito, slug=slug)

@app.route('/<slug>/agregar_cursos', methods=['POST'])
def agregar_cursos(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    cursos = request.form.getlist('cursos')
    extra  = request.form.get('cursos_extra', '').strip()
    if extra:
        cursos += [c.strip() for c in extra.split(',') if c.strip()]
    conn = conectar(slug)
    for c in cursos:
        if c:
            conn.execute('INSERT OR IGNORE INTO asignaciones (profesor_id,curso) VALUES (?,?)', (prof['id'], c))
    conn.commit(); conn.close()
    return redirect(url_for('cambiar_password', slug=slug))

@app.route('/<slug>/quitar_curso/<curso>')
def quitar_curso(slug, curso):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    conn = conectar(slug)
    conn.execute('DELETE FROM asignaciones WHERE profesor_id=? AND curso=?', (prof['id'], curso))
    conn.commit(); conn.close()
    return redirect(url_for('cambiar_password', slug=slug))

# ── ESTUDIANTE ────────────────────────────────────────────────────────────────

@app.route('/<slug>/estudiante')
def vista_estudiante(slug):
    require_colegio(slug)
    if session.get(f'rol_{slug}') != 'estudiante': return redirect(url_for('login', slug=slug))
    aid = session.get(f'alumno_id_{slug}')
    conn = conectar(slug)
    alumno = conn.execute('SELECT * FROM alumnos WHERE id=?',(aid,)).fetchone()
    asis   = conn.execute('SELECT estado FROM asistencia WHERE aid=? ORDER BY id DESC LIMIT 1',(aid,)).fetchone()
    agenda = conn.execute('SELECT * FROM compromisos WHERE curso=? ORDER BY materia,fecha',(alumno['curso'],)).fetchall()
    notas_raw = conn.execute(
        '''SELECT ac.materia, ac.nombre as act_nombre, ac.orden, n.val
           FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
           WHERE n.aid=? ORDER BY ac.materia, ac.orden''', (aid,)
    ).fetchall()
    evals_raw = conn.execute('SELECT e.materia, e.evaluacion, e.autoevaluacion FROM evaluaciones e WHERE e.aid=?', (aid,)).fetchall()
    evals_map = {e['materia']: dict(e) for e in evals_raw}
    conn.close()
    notas_pm = {}
    for nr in notas_raw:
        notas_pm.setdefault(nr['materia'],[]).append({'actividad':nr['act_nombre'],'val':nr['val']})
    for mat in evals_map:
        if mat not in notas_pm: notas_pm[mat] = []
    total = sum(len(v) for v in notas_pm.values())
    prom  = round(sum(n['val'] for v in notas_pm.values() for n in v)/total,2) if total else 0
    return render_template('estudiante.html',
        alumno=alumno, notas_por_materia=notas_pm, evals_map=evals_map,
        promedio=prom, asistencia=asis['estado'] if asis else '-',
        agenda=agenda, slug=slug)

@app.route('/<slug>/horarios')
def horarios(slug):
    require_colegio(slug)
    if not session.get(f'rol_{slug}'): return redirect(url_for('login', slug=slug))
    return render_template('horarios.html', slug=slug)

# ── STATIC ────────────────────────────────────────────────────────────────────

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'static'), filename)

# ── REDIRECT RAÍZ ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index_root.html')

# ── PÁGINAS DE ERROR ──────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', codigo=404, mensaje='Colegio no encontrado.'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', codigo=403, mensaje='Este colegio está inactivo. Contacta a Lumini.'), 403

# ── INICIALIZAR ───────────────────────────────────────────────────────────────
init_master_db()
