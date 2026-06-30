import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, send_file, abort, jsonify
import sqlite3, hashlib, time, secrets, logging, json, uuid, bcrypt
from datetime import timedelta, datetime
from io import BytesIO
import html
app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400  # Cache 24 horas
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(hours=4)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'

@app.template_filter('parse_json')
def parse_json_filter(val):
    try: return json.loads(val) if val else {}
    except Exception: return {}

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

def extension_permitida(filename):
    ext = ('.' + filename.rsplit('.', 1)[-1]).lower() if '.' in filename else ''
    return ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp')

def validar_imagen(ruta):
    try:
        from PIL import Image
        img = Image.open(ruta)
        img.verify()
        return True
    except Exception:
        return False

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
    _purgar_intentos_antiguos()
    clave = f'{prefijo}_{ip}'
    d = login_intentos.setdefault(clave, {'intentos': 0, 'bloqueado_hasta': None})
    d['intentos'] += 1
    if d['intentos'] >= 5:
        d['bloqueado_hasta'] = time.time() + 300
        logger.warning(f"IP bloqueada por fuerza bruta: {ip} (ctx={prefijo})")
    return d['intentos']

def _purgar_intentos_antiguos():
    ahora = time.time()
    viejas = [k for k, v in login_intentos.items()
              if v['bloqueado_hasta'] and ahora > v['bloqueado_hasta'] + 3600]
    for k in viejas:
        del login_intentos[k]

def limpiar_intentos(ip, prefijo=''):
    login_intentos.pop(f'{prefijo}_{ip}', None)

# ── HASH ──────────────────────────────────────────────────────────────────────
def hash_pw(pw, _sal=None):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verificar_pw(plano, guardada):
    if not guardada: return False
    if guardada.startswith('$2b$') or guardada.startswith('$2a$'):
        return bcrypt.checkpw(plano.encode(), guardada.encode())
    if '$' in guardada:
        partes = guardada.split('$', 1)
        if len(partes) == 2:
            sal, h = partes
            return hashlib.sha256((sal + plano).encode()).hexdigest() == h
        return False
    return hashlib.sha256(plano.encode()).hexdigest() == guardada

def necesita_rehash(guardada):
    return not (guardada.startswith('$2b$') or guardada.startswith('$2a$'))

# ── SCHEMA VERSIONING ──────────────────────────────────────────────────────────
SCHEMA_VERSION = 10

def _ejecutar_migraciones(slug, conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS schema_meta (
        version INTEGER PRIMARY KEY,
        applied_at TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.commit()
    row = conn.execute('SELECT COALESCE(MAX(version), 0) as v FROM schema_meta').fetchone()
    current = row['v'] if row else 0
    for v in range(current + 1, SCHEMA_VERSION + 1):
        mig_fn = MIGRACIONES.get(v)
        if mig_fn:
            logger.info(f"[{slug}] Migrando a versión {v}...")
            mig_fn(conn, slug)
            conn.execute('INSERT OR IGNORE INTO schema_meta (version) VALUES (?)', (v,))
            conn.commit()
            logger.info(f"[{slug}] Versión {v} aplicada.")

def _migrar_v6(conn, slug=None):
    conn.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL,
        email TEXT NOT NULL,
        password_hash TEXT,
        nombre TEXT NOT NULL,
        apellido TEXT DEFAULT '',
        tipo_documento TEXT DEFAULT '',
        documento TEXT DEFAULT '',
        telefono TEXT DEFAULT '',
        avatar TEXT DEFAULT '',
        activo INTEGER DEFAULT 1,
        creado TEXT DEFAULT (datetime('now','localtime')),
        actualizado TEXT DEFAULT (datetime('now','localtime')),
        ultimo_acceso TEXT,
        UNIQUE(slug, email)
    )''')

def _migrar_v7(conn, slug=None):
    conn.execute('''CREATE TABLE IF NOT EXISTS roles_base (
        codigo TEXT PRIMARY KEY,
        nombre_default TEXT NOT NULL,
        nivel INTEGER NOT NULL,
        descripcion TEXT
    )''')
    roles_default = [
        ('admin',     'Administrador',     0, 'Acceso global al sistema'),
        ('rector',    'Rector',            1, 'Máxima autoridad institucional'),
        ('authority', 'Autoridad Académica',2, 'Coordinadores, decanos, directores'),
        ('teacher',   'Docente',           3, 'Profesores e instructores'),
        ('student',   'Estudiante',         4, 'Alumnos y participantes'),
        ('guardian',  'Acudiente',          5, 'Padres y representantes'),
    ]
    for cod, nom, niv, desc in roles_default:
        conn.execute('INSERT OR IGNORE INTO roles_base (codigo, nombre_default, nivel, descripcion) VALUES (?,?,?,?)',
                    (cod, nom, niv, desc))
    conn.execute('''CREATE TABLE IF NOT EXISTS roles_instancia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL,
        codigo TEXT NOT NULL,
        nombre TEXT NOT NULL,
        jerarquia INTEGER DEFAULT 1,
        activo INTEGER DEFAULT 1,
        UNIQUE(slug, codigo)
    )''')

def _migrar_v8(conn, slug=None):
    conn.execute('''CREATE TABLE IF NOT EXISTS usuarios_roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        rol_id INTEGER NOT NULL,
        entidad_tipo TEXT,
        entidad_id INTEGER,
        asignado_por INTEGER,
        creado TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(usuario_id, rol_id, entidad_tipo, entidad_id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS password_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        token TEXT UNIQUE NOT NULL,
        expira TEXT NOT NULL,
        usado INTEGER DEFAULT 0,
        creado TEXT DEFAULT (datetime('now','localtime'))
    )''')

def _migrar_v9(conn, slug=None):
    conn.execute('''CREATE TABLE IF NOT EXISTS config_institucion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL UNIQUE,
        tipo_evaluacion TEXT DEFAULT 'numerica',
        escala_min REAL DEFAULT 1.0,
        escala_max REAL DEFAULT 10.0,
        nota_minima_aprobar REAL DEFAULT 6.0,
        decimales_notas INTEGER DEFAULT 1,
        creditos_activo INTEGER DEFAULT 0,
        escala_conceptual TEXT DEFAULT '["A","B","C","D","E","F"]',
        num_periodos INTEGER DEFAULT 4,
        periodos_json TEXT,
        jornadas_json TEXT,
        jerarquia_activa INTEGER DEFAULT 0,
        niveles_json TEXT,
        roles_json TEXT,
        acuse_recibo INTEGER DEFAULT 1,
        firmas_activas INTEGER DEFAULT 0,
        notas_publicas_entre_pares INTEGER DEFAULT 0,
        idioma TEXT DEFAULT 'es',
        huso_horario TEXT DEFAULT 'America/Bogota',
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    )''')
    if slug:
        conn.execute('''INSERT OR IGNORE INTO config_institucion
            (slug, num_periodos, jornadas_json, roles_json)
            VALUES (?, 4, '["Mañana","Tarde","Nocturna"]',
            '{"rector":"Rector","authority":"Coordinador","teacher":"Docente","student":"Estudiante","guardian":"Acudiente"}')''',
            (slug,))

def _migrar_v10(conn, slug=None):
    conn.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        accion TEXT NOT NULL,
        tabla TEXT NOT NULL,
        registro_id INTEGER,
        valor_anterior TEXT,
        valor_nuevo TEXT,
        ip TEXT,
        user_agent TEXT,
        creado TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_tabla ON audit_log(tabla, registro_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_usuario ON audit_log(usuario_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_fecha ON audit_log(creado)')
    conn.execute('''CREATE TABLE IF NOT EXISTS estructura_academica (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL,
        nivel INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        nombre_tipo TEXT DEFAULT '',
        padre_id INTEGER,
        activo INTEGER DEFAULT 1,
        UNIQUE(slug, nivel, nombre)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS curso_nuevo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL,
        estructura_id INTEGER,
        nombre TEXT NOT NULL,
        jornada TEXT DEFAULT 'Mañana',
        activo INTEGER DEFAULT 1
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS materias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL,
        nombre TEXT NOT NULL,
        activo INTEGER DEFAULT 1,
        UNIQUE(slug, nombre)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS curso_materias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        curso_id INTEGER NOT NULL,
        materia_id INTEGER NOT NULL,
        docente_id INTEGER,
        UNIQUE(curso_id, materia_id)
    )''')

MIGRACIONES = {
    6:  _migrar_v6,
    7:  _migrar_v7,
    8:  _migrar_v8,
    9:  _migrar_v9,
    10: _migrar_v10,
}

# ── MASTER DB ─────────────────────────────────────────────────────────────────
def conectar_master():
    c = sqlite3.connect(MASTER_DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA foreign_keys=ON')
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
        codigo_registro TEXT DEFAULT '',
        primary_color TEXT DEFAULT '#6c63ff',
        secondary_color TEXT DEFAULT '#3498db'
    )''')
    # Migraciones de columnas nuevas
    for col in [
        'logo TEXT DEFAULT ""',
        'vencimiento TEXT DEFAULT NULL',
        'num_periodos INTEGER DEFAULT 4',
        'codigo_registro TEXT DEFAULT ""',
        'primary_color TEXT DEFAULT "#6c63ff"',
        'secondary_color TEXT DEFAULT "#3498db"',
        'codigo_profesores TEXT DEFAULT ""',
        'codigo_directoras TEXT DEFAULT ""',
        'codigo_rectores TEXT DEFAULT ""',
        'schema_version INTEGER DEFAULT 0',
    ]:
        try: conn.execute(f'ALTER TABLE colegios ADD COLUMN {col}')
        except sqlite3.OperationalError:
            logger.debug(f'Columna ya existe en colegios: {col.split()[0]}')
    # Migrar codigo_registro a las columnas específicas si están vacías
    for c in conn.execute('SELECT slug, codigo_registro, codigo_profesores, codigo_directoras, codigo_rectores FROM colegios').fetchall():
        updates = []
        if c['codigo_registro'] and not c['codigo_profesores']:
            updates.append(('codigo_profesores', c['codigo_registro']))
        if c['codigo_registro'] and not c['codigo_directoras']:
            updates.append(('codigo_directoras', c['codigo_registro']))
        if c['codigo_registro'] and not c['codigo_rectores']:
            updates.append(('codigo_rectores', c['codigo_registro']))
        for col_name, val in updates:
            conn.execute(f'UPDATE colegios SET {col_name}=? WHERE slug=?', (val, c['slug']))
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

def get_codigo_registro(slug, rol=None):
    """Devuelve el código de invitación del colegio para un rol específico.
    rol: 'profesores', 'directoras', 'rectores' o None (usa codigo_registro genérico)."""
    c = get_colegio(slug)
    if not c: return ''
    if rol == 'profesores':
        val = c['codigo_profesores'] or c['codigo_registro'] or ''
    elif rol == 'directoras':
        val = c['codigo_directoras'] or c['codigo_registro'] or ''
    elif rol == 'rectores':
        val = c['codigo_rectores'] or c['codigo_registro'] or ''
    else:
        val = c['codigo_registro'] or ''
    return val

# ── DB POR COLEGIO ────────────────────────────────────────────────────────────
def db_path(slug): return os.path.join(DB_FOLDER, f'{slug}.db')

def conectar(slug):
    c = sqlite3.connect(db_path(slug), timeout=30)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA foreign_keys=ON')
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
        if 'pin' not in cols_alum:
            conn.execute('ALTER TABLE alumnos ADD COLUMN pin TEXT DEFAULT ""')
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
        except sqlite3.OperationalError:
            logger.warning(f'[{slug}] Recreando tabla horarios_curso (schema legacy)')
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

        cols_rec = [r[1] for r in conn.execute('PRAGMA table_info(rectores)').fetchall()]
        if 'es_principal' not in cols_rec:
            conn.execute('ALTER TABLE rectores ADD COLUMN es_principal INTEGER DEFAULT 0')
            conn.commit()
        if 'jornada' not in cols_rec:
            conn.execute('ALTER TABLE rectores ADD COLUMN jornada TEXT DEFAULT ""')
            conn.commit()

        cols_cl = [r[1] for r in conn.execute('PRAGMA table_info(comunicaciones_leidas)').fetchall()]
        if 'leido' not in cols_cl:
            conn.execute('ALTER TABLE comunicaciones_leidas ADD COLUMN leido INTEGER DEFAULT 0')
            conn.commit()

        tablas_actuales = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        if 'profesores' not in tablas_actuales:
            return
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
        logger.error(f'[{slug}] Error en migración legacy: {e}', exc_info=True)
        raise
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
            email_acudiente TEXT DEFAULT '',
            pin TEXT DEFAULT '')''',
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
        '''CREATE TABLE IF NOT EXISTS rectores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL, usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, email TEXT DEFAULT '',
            activo INTEGER DEFAULT 1,
            es_principal INTEGER DEFAULT 0,
            pregunta_secreta TEXT DEFAULT '',
            respuesta_secreta TEXT DEFAULT '')''',
        '''CREATE TABLE IF NOT EXISTS comunicaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rector_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            contenido TEXT NOT NULL,
            destinatario_tipo TEXT NOT NULL,
            destinatario_valor TEXT DEFAULT '',
            prioridad TEXT NOT NULL DEFAULT 'normal',
            estado TEXT NOT NULL DEFAULT 'borrador',
            fecha_creacion TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            fecha_programada TEXT DEFAULT NULL,
            fecha_publicacion TEXT DEFAULT NULL,
            activo INTEGER DEFAULT 1)''',
        '''CREATE TABLE IF NOT EXISTS comunicaciones_leidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comunicacion_id INTEGER NOT NULL,
            usuario_tipo TEXT NOT NULL,
            usuario_id INTEGER NOT NULL,
            leido INTEGER DEFAULT 0,
            fecha_lectura TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(comunicacion_id, usuario_tipo, usuario_id))''',
        '''CREATE TABLE IF NOT EXISTS notificaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_tipo TEXT NOT NULL,
            usuario_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            mensaje TEXT DEFAULT '',
            tipo TEXT NOT NULL DEFAULT 'info',
            link TEXT DEFAULT '',
            leida INTEGER DEFAULT 0,
            fecha_creacion TEXT NOT NULL DEFAULT (datetime('now','localtime')))''',
        '''CREATE TABLE IF NOT EXISTS canales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL,
            rector_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            nombre TEXT NOT NULL,
            descripcion TEXT DEFAULT '',
            curso TEXT DEFAULT '',
            materia TEXT DEFAULT '',
            activo INTEGER DEFAULT 1,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime')))''',
        '''CREATE TABLE IF NOT EXISTS canal_miembros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canal_id INTEGER NOT NULL,
            usuario_tipo TEXT NOT NULL,
            usuario_id INTEGER NOT NULL,
            fecha_ingreso TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(canal_id, usuario_tipo, usuario_id))''',
        '''CREATE TABLE IF NOT EXISTS mensajes_canal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canal_id INTEGER NOT NULL,
            usuario_tipo TEXT NOT NULL,
            usuario_id INTEGER NOT NULL,
            mensaje TEXT NOT NULL,
            fecha TEXT DEFAULT (datetime('now','localtime')),
            editado INTEGER DEFAULT 0)''',
        '''CREATE TABLE IF NOT EXISTS mensajes_leidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mensaje_id INTEGER NOT NULL,
            usuario_tipo TEXT NOT NULL,
            usuario_id INTEGER NOT NULL,
            fecha_lectura TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(mensaje_id, usuario_tipo, usuario_id))''',
        '''CREATE TABLE IF NOT EXISTS periodos_estado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo INTEGER NOT NULL UNIQUE,
            estado TEXT NOT NULL DEFAULT 'abierto',
            fecha_apertura TEXT,
            fecha_cierre TEXT,
            abierto_por INTEGER,
            cerrado_por INTEGER)''',
        '''CREATE TABLE IF NOT EXISTS solicitudes_modificacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo INTEGER NOT NULL,
            aid INTEGER NOT NULL,
            actividad_id INTEGER,
            campo TEXT DEFAULT 'nota',
            materia TEXT,
            nota_actual REAL,
            nota_solicitada REAL NOT NULL,
            motivo TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            solicitado_por INTEGER NOT NULL,
            revisado_por INTEGER,
            respuesta TEXT,
            creado TEXT DEFAULT (datetime('now','localtime')),
            actualizado TEXT DEFAULT (datetime('now','localtime')))''',
        # ── Fase 5 – Comunicación v2 ─────────────────────────────────
        '''CREATE TABLE IF NOT EXISTS mensajes_archivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mensaje_id INTEGER,
            canal_id INTEGER NOT NULL,
            usuario_tipo TEXT NOT NULL,
            usuario_id INTEGER NOT NULL,
            nombre_original TEXT NOT NULL,
            nombre_archivo TEXT NOT NULL,
            tipo_mime TEXT NOT NULL,
            tamano INTEGER NOT NULL,
            es_imagen INTEGER DEFAULT 0,
            ancho INTEGER,
            alto INTEGER,
            fecha TEXT DEFAULT (datetime('now','localtime')))''',
        '''CREATE TABLE IF NOT EXISTS mensajes_reacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mensaje_id INTEGER NOT NULL,
            usuario_tipo TEXT NOT NULL,
            usuario_id INTEGER NOT NULL,
            reaccion TEXT NOT NULL,
            fecha TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(mensaje_id, usuario_tipo, usuario_id, reaccion))''',
        '''CREATE TABLE IF NOT EXISTS mensajes_fijados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canal_id INTEGER NOT NULL,
            mensaje_id INTEGER NOT NULL,
            fijado_por_tipo TEXT NOT NULL,
            fijado_por_id INTEGER NOT NULL,
            fecha TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(canal_id, mensaje_id))''',
        '''CREATE TABLE IF NOT EXISTS canal_enlaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canal_id INTEGER NOT NULL,
            titulo TEXT,
            url TEXT NOT NULL,
            agregado_por_tipo TEXT NOT NULL,
            agregado_por_id INTEGER NOT NULL,
            fecha TEXT DEFAULT (datetime('now','localtime')))''',
        '''CREATE TABLE IF NOT EXISTS canal_actividad (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canal_id INTEGER NOT NULL,
            usuario_tipo TEXT NOT NULL,
            usuario_id INTEGER NOT NULL,
            estado TEXT DEFAULT 'online',
            ultima_vista TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(canal_id, usuario_tipo, usuario_id))''',
    ]
    for s in stmts:
        try: conn.execute(s)
        except sqlite3.OperationalError as e:
            logger.warning(f'init_db table: {e}')
    alter_stmts = [
        "ALTER TABLE mensajes_canal ADD COLUMN responde_a INTEGER REFERENCES mensajes_canal(id)",
        "ALTER TABLE mensajes_canal ADD COLUMN editado_en TEXT",
        "ALTER TABLE mensajes_canal ADD COLUMN eliminado INTEGER DEFAULT 0",
        "ALTER TABLE mensajes_canal ADD COLUMN tiene_archivos INTEGER DEFAULT 0",
        "ALTER TABLE config_institucion ADD COLUMN max_tamano_archivo INTEGER DEFAULT 10485760",
    ]
    for stmt in alter_stmts:
        try: conn.execute(stmt)
        except sqlite3.OperationalError:
            pass
    indexes = [
        'CREATE INDEX IF NOT EXISTS idx_notas_aid ON notas(aid)',
        'CREATE INDEX IF NOT EXISTS idx_notas_actividad ON notas(actividad_id)',
        'CREATE INDEX IF NOT EXISTS idx_asistencia_aid ON asistencia(aid)',
        'CREATE INDEX IF NOT EXISTS idx_observaciones_aid ON observaciones(aid)',
        'CREATE INDEX IF NOT EXISTS idx_evaluaciones_aid ON evaluaciones(aid)',
        'CREATE INDEX IF NOT EXISTS idx_actividades_prof ON actividades(profesor_id,materia,curso,jornada,periodo)',
        'CREATE INDEX IF NOT EXISTS idx_alumnos_nombre ON alumnos(nombre,jornada)',
        'CREATE INDEX IF NOT EXISTS idx_mensajes_canal ON mensajes_canal(canal_id, id)',
        'CREATE INDEX IF NOT EXISTS idx_archivos_canal ON mensajes_archivos(canal_id, mensaje_id)',
        'CREATE INDEX IF NOT EXISTS idx_archivos_mensaje ON mensajes_archivos(mensaje_id)',
        'CREATE INDEX IF NOT EXISTS idx_reacciones_mensaje ON mensajes_reacciones(mensaje_id)',
        'CREATE INDEX IF NOT EXISTS idx_fijados_canal ON mensajes_fijados(canal_id)',
        'CREATE INDEX IF NOT EXISTS idx_enlaces_canal ON canal_enlaces(canal_id)',
        'CREATE INDEX IF NOT EXISTS idx_actividad_canal ON canal_actividad(canal_id)',
    ]
    for idx in indexes:
        try: conn.execute(idx)
        except sqlite3.OperationalError as e:
            logger.warning(f'init_db index: {e}')
    conn.commit()
    _ejecutar_migraciones(slug, conn)
    conn.close()
    migrar_db(slug)

# ── HELPERS ───────────────────────────────────────────────────────────────────
def get_profesor(slug):
    pid = session.get(f'profesor_id_{slug}')
    if not pid: return None
    conn = conectar(slug)
    p = conn.execute('SELECT * FROM profesores WHERE id=? AND activo=1', (pid,)).fetchone()
    conn.close()
    if not p:
        session.pop(f'profesor_id_{slug}', None)
        session.pop(f'rol_{slug}', None)
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

# ── CANALES HELPERS ─────────────────────────────────────────────────────────────
def get_usuario_actual(slug):
    prof = get_profesor(slug)
    if prof: return ('profesor', prof['id'])
    aid = session.get(f'alumno_id_{slug}')
    if aid: return ('estudiante', aid)
    direc = get_directora(slug)
    if direc: return ('directora', direc['id'])
    rector = get_rector(slug)
    if rector: return ('rector', rector['id'])
    return (None, None)

# ── PERMISSION SYSTEM ────────────────────────────────────────────────────────
def obtener_roles_usuario(slug, usuario_id):
    conn = conectar(slug)
    rows = conn.execute('''
        SELECT r.codigo, ri.nombre as rol_nombre, ri.jerarquia,
               ur.entidad_tipo, ur.entidad_id
        FROM usuarios_roles ur
        JOIN roles_instancia ri ON ri.id = ur.rol_id
        JOIN roles_base r ON r.codigo = ri.codigo
        WHERE ur.usuario_id = ? AND ri.activo = 1
    ''', (usuario_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

PERMISOS_POR_CODIGO = {
    'admin':     ['*'],
    'rector':    ['*'],
    'authority': ['people.teachers.view', 'people.students.view',
        'structure.courses.manage', 'structure.subjects.manage',
        'academic.grades.view', 'academic.grades.write', 'academic.grades.approve',
        'academic.grades.history', 'academico.periodos.cerrar',
        'academico.periodos.abrir', 'academico.notas.aprobar',
        'academico.notas.modificar_cerrado',
        'academic.attendance.view',
        'academic.observations.view', 'academic.observations.write',
        'academic.evaluations.create', 'academic.evaluations.edit',
        'communication.communicados.view', 'communication.communicados.create',
        'communication.channels.read', 'communication.channels.send',
        'reports.grades', 'reports.attendance', 'reports.export',
        'audit.log.view'],
    'teacher': ['people.students.view',
        'academic.grades.view', 'academic.grades.write',
        'academic.attendance.view', 'academic.attendance.write',
        'academic.observations.view', 'academic.observations.write',
        'academic.evaluations.create', 'academic.evaluations.edit',
        'academic.activities.create', 'academic.activities.edit',
        'communication.communicados.view',
        'communication.channels.read', 'communication.channels.send'],
    'student': ['academic.grades.view', 'academic.attendance.view',
        'communication.communicados.view',
        'communication.channels.read', 'communication.channels.send'],
    'guardian': ['academic.grades.view', 'academic.attendance.view',
        'communication.communicados.view',
        'communication.channels.read'],
}

NIVELES_ROL = {'admin': 0, 'rector': 1, 'authority': 2, 'teacher': 3, 'student': 4, 'guardian': 5}

def _permisos_para_rol(codigo):
    permisos = set()
    nivel = NIVELES_ROL.get(codigo, 99)
    for rc, rn in NIVELES_ROL.items():
        if rn >= nivel:
            permisos.update(PERMISOS_POR_CODIGO.get(rc, []))
    return list(permisos)

def tiene_permiso(slug, usuario_id, permiso, entidad_tipo=None, entidad_id=None):
    roles = obtener_roles_usuario(slug, usuario_id)
    for rol in roles:
        if rol['codigo'] in ('admin', 'rector'):
            return True
        if permiso not in _permisos_para_rol(rol['codigo']) and '*' not in _permisos_para_rol(rol['codigo']):
            continue
        if entidad_tipo and rol['entidad_tipo']:
            if rol['entidad_tipo'] != entidad_tipo or rol['entidad_id'] != entidad_id:
                continue
        return True
    return False

from functools import wraps

def requiere_permiso(permiso, obtener_entidad=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            slug = kwargs.get('slug')
            if not slug: abort(400)
            usuario_tipo, usuario_id = get_usuario_actual(slug)
            if not usuario_id:
                return redirect(url_for('login', slug=slug))
            if obtener_entidad:
                e_tipo, e_id = obtener_entidad(kwargs)
            else:
                e_tipo, e_id = None, None
            if not tiene_permiso(slug, usuario_id, permiso, e_tipo, e_id):
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ── PERIOD HELPERS ────────────────────────────────────────────────────────────
def periodo_cerrado(slug, periodo, conn=None):
    cerrar_propia = conn or conectar(slug)
    try:
        row = cerrar_propia.execute(
            'SELECT estado FROM periodos_estado WHERE periodo=?',
            (periodo,)).fetchone()
        return row is not None and row['estado'] == 'cerrado'
    finally:
        if not conn: cerrar_propia.close()

# ── AUDIT HELPER ──────────────────────────────────────────────────────────────
def audit_log(slug, usuario_id, accion, tabla, registro_id=None, valor_anterior=None, valor_nuevo=None):
    from flask import request as flask_request
    conn = None
    try:
        conn = conectar(slug)
        conn.execute(
            '''INSERT INTO audit_log (usuario_id, accion, tabla, registro_id, valor_anterior, valor_nuevo, ip, user_agent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (usuario_id, accion, tabla, registro_id,
             json.dumps(valor_anterior) if valor_anterior else None,
             json.dumps(valor_nuevo) if valor_nuevo else None,
             flask_request.remote_addr,
             flask_request.user_agent.string if flask_request.user_agent else None)
        )
        conn.commit()
    except Exception as e:
        logger.warning(f"[audit] {e}")
    finally:
        if conn: conn.close()

# ── CONFIG HELPERS ────────────────────────────────────────────────────────────
def config_get(slug):
    conn = conectar(slug)
    c = conn.execute('SELECT * FROM config_institucion WHERE slug=?', (slug,)).fetchone()
    conn.close()
    return dict(c) if c else {}

def config_get_nombre_rol(slug, codigo):
    config = config_get(slug)
    roles = {}
    try: roles = json.loads(config.get('roles_json', '{}'))
    except (json.JSONDecodeError, TypeError): pass
    return roles.get(codigo, codigo.capitalize())

def config_get_nombre_institucion(slug):
    inst = get_colegio(slug)
    return inst['nombre'] if inst else slug

# ── CANALES HELPERS ─────────────────────────────────────────────────────────────
def canales_usuario(slug, usuario_tipo, usuario_id):
    conn = conectar(slug)
    rows = conn.execute('''
        SELECT c.*,
            (SELECT mensaje FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_mensaje,
            (SELECT usuario_tipo FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_autor_tipo,
            (SELECT usuario_id FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_autor_id,
            (SELECT fecha FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultima_fecha,
            (SELECT COUNT(*) FROM mensajes_canal mc
             LEFT JOIN mensajes_leidos ml ON ml.mensaje_id=mc.id AND ml.usuario_tipo=? AND ml.usuario_id=?
             WHERE mc.canal_id=c.id AND ml.id IS NULL) as no_leidos
        FROM canales c
        JOIN canal_miembros cm ON cm.canal_id=c.id
        WHERE cm.usuario_tipo=? AND cm.usuario_id=? AND c.activo=1
        ORDER BY ultima_fecha DESC''', (usuario_tipo, usuario_id, usuario_tipo, usuario_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def agregar_miembro_canal(conn, canal_id, usuario_tipo, usuario_id):
    conn.execute('INSERT OR IGNORE INTO canal_miembros (canal_id, usuario_tipo, usuario_id) VALUES (?,?,?)',
                 (canal_id, usuario_tipo, usuario_id))

def asignar_miembros_auto(conn, slug, canal_id, tipo, curso='', materia=''):
    if tipo in ('institucional','rectoria','profesores'):
        for p in conn.execute('SELECT id FROM profesores WHERE activo=1').fetchall():
            agregar_miembro_canal(conn, canal_id, 'profesor', p['id'])
    if tipo == 'institucional':
        for a in conn.execute('SELECT id FROM alumnos WHERE activo=1').fetchall():
            agregar_miembro_canal(conn, canal_id, 'estudiante', a['id'])
    elif tipo == 'director_curso' and curso:
        for d in conn.execute('SELECT id FROM directoras WHERE curso=? AND activo=1', (curso,)).fetchall():
            agregar_miembro_canal(conn, canal_id, 'directora', d['id'])
        for p in conn.execute('SELECT DISTINCT profesor_id FROM asignaciones_curso WHERE curso=?', (curso,)).fetchall():
            agregar_miembro_canal(conn, canal_id, 'profesor', p['profesor_id'])
    elif tipo == 'curso' and curso:
        for p in conn.execute('SELECT DISTINCT profesor_id FROM asignaciones_curso WHERE curso=?', (curso,)).fetchall():
            agregar_miembro_canal(conn, canal_id, 'profesor', p['profesor_id'])
        for a in conn.execute('SELECT id FROM alumnos WHERE curso=? AND activo=1', (curso,)).fetchall():
            agregar_miembro_canal(conn, canal_id, 'estudiante', a['id'])
    elif tipo == 'materia' and materia:
        for p in conn.execute('SELECT DISTINCT profesor_id FROM asignaciones_materia WHERE materia=?', (materia,)).fetchall():
            agregar_miembro_canal(conn, canal_id, 'profesor', p['profesor_id'])
        for cr in conn.execute('SELECT DISTINCT curso FROM actividades WHERE materia=?', (materia,)).fetchall():
            for a in conn.execute('SELECT id FROM alumnos WHERE curso=? AND activo=1', (cr['curso'],)).fetchall():
                agregar_miembro_canal(conn, canal_id, 'estudiante', a['id'])
    rector = get_rector(slug)
    if rector:
        agregar_miembro_canal(conn, canal_id, 'rector', rector['id'])

def nombre_usuario_canal(conn, tipo, uid):
    if tipo == 'profesor':
        r = conn.execute('SELECT nombre FROM profesores WHERE id=?', (uid,)).fetchone()
    elif tipo == 'estudiante':
        r = conn.execute('SELECT nombre FROM alumnos WHERE id=?', (uid,)).fetchone()
    elif tipo == 'rector':
        r = conn.execute('SELECT nombre FROM rectores WHERE id=?', (uid,)).fetchone()
    elif tipo == 'directora':
        r = conn.execute('SELECT nombre FROM directoras WHERE id=?', (uid,)).fetchone()
    else:
        return 'Desconocido'
    return r['nombre'] if r else 'Desconocido'

# ── FILE STORAGE (Fase 5) ─────────────────────────────────────────────────────
def max_tamano_archivo(slug):
    conn = conectar(slug)
    cfg = conn.execute('SELECT max_tamano_archivo FROM config_institucion WHERE slug=?', (slug,)).fetchone()
    conn.close()
    return cfg['max_tamano_archivo'] if cfg else 10485760

EXTENSIONES_PERMITIDAS = {
    '.pdf': 'application/pdf',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xls': 'application/vnd.ms-excel',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.ppt': 'application/vnd.ms-powerpoint',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp',
    '.svg': 'image/svg+xml',
    '.txt': 'text/plain',
    '.csv': 'text/csv',
    '.zip': 'application/zip',
}

def guardar_archivo_mensaje(slug, canal_id, f, usuario_tipo, usuario_id):
    import os
    nombre_original = f.filename
    ext = os.path.splitext(nombre_original)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        return None, 'Extensión no permitida'
    tamano = len(f.read())
    f.seek(0)
    max_sz = max_tamano_archivo(slug)
    if tamano > max_sz:
        return None, f'Archivo muy grande (máx {max_sz//1048576} MB)'
    es_img = ext in ('.jpg','.jpeg','.png','.gif','.webp')
    if es_img:
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(f.read()))
            img.verify()
            f.seek(0)
        except Exception:
            return None, 'Archivo de imagen inválido o corrupto'
    nombre_archivo = f'{uuid.uuid4().hex}{ext}'
    upload_dir = os.path.join(app.root_path, 'static', 'uploads', slug)
    os.makedirs(upload_dir, exist_ok=True)
    ruta = os.path.join(upload_dir, nombre_archivo)
    f.save(ruta)
    ancho = alto = None
    if es_img:
        try:
            from PIL import Image
            img = Image.open(ruta)
            ancho, alto = img.size
        except Exception: pass
    conn = conectar(slug)
    try:
        fid = conn.execute(
            '''INSERT INTO mensajes_archivos
               (canal_id, usuario_tipo, usuario_id, nombre_original, nombre_archivo, tipo_mime, tamano, es_imagen, ancho, alto)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (canal_id, usuario_tipo, usuario_id, nombre_original, nombre_archivo,
             EXTENSIONES_PERMITIDAS[ext], tamano, 1 if es_img else 0, ancho, alto)).lastrowid
        conn.commit()
    finally:
        conn.close()
    return fid, None

def archivos_por_mensaje(conn, mensaje_id):
    return [dict(r) for r in conn.execute(
        'SELECT * FROM mensajes_archivos WHERE mensaje_id=? ORDER BY id', (mensaje_id,)).fetchall()]

def reacciones_por_mensaje(conn, mensaje_id):
    rows = conn.execute(
        'SELECT reaccion, usuario_tipo, usuario_id FROM mensajes_reacciones WHERE mensaje_id=?',
        (mensaje_id,)).fetchall()
    result = {}
    for r in rows:
        result.setdefault(r['reaccion'], []).append({'tipo': r['usuario_tipo'], 'id': r['usuario_id']})
    return result

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
    try:
        pri_color = colors.HexColor(colegio['primary_color']) if colegio and colegio['primary_color'] else colors.HexColor('#6c63ff')
    except (KeyError, AttributeError, TypeError):
        pri_color = colors.HexColor('#6c63ff')
    try:
        sec_color = colors.HexColor(colegio['secondary_color']) if colegio and colegio['secondary_color'] else colors.HexColor('#3498db')
    except (KeyError, AttributeError, TypeError):
        sec_color = colors.HexColor('#3498db')
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('t', fontSize=16, fontName='Helvetica-Bold',
                                  textColor=pri_color, spaceAfter=4)
    sub_style    = ParagraphStyle('s', fontSize=10, fontName='Helvetica',
                                  textColor=colors.grey, spaceAfter=10)
    mat_style    = ParagraphStyle('m', fontSize=11, fontName='Helvetica-Bold',
                                  textColor=pri_color, spaceBefore=10, spaceAfter=4)
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
            ('BACKGROUND', (0, 0), (-1, 0), pri_color),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, -1), 9),
            ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
            ('GRID',       (0, 0), (-1, -1), 0.3, colors.HexColor('#cccccc')),
        ]))
        story.append(t)
        if final is not None: todos_finales.append(final)

    prom_general = round(sum(todos_finales) / len(todos_finales), 2) if todos_finales else None
    story.append(Spacer(1, 0.5*cm))
    estado = 'Pendiente' if prom_general is None else ('Aprobado' if prom_general >= 3.0 else 'Reprobado')
    bg_color = pri_color if prom_general is not None and prom_general >= 3.0 else colors.HexColor('#e74c3c') if prom_general is not None else colors.HexColor('#64748B')
    resumen = Table(
        [['PROMEDIO GENERAL', str(prom_general) if prom_general is not None else '—', 'ESTADO', estado]],
        colWidths=[5*cm, 3*cm, 3*cm, 3*cm]
    )
    resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg_color),
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
            if not validar_csrf():
                error = 'Error de seguridad.'
                return render_template('admin_login.html', error=error)
            bloqueado = ip_bloqueada(ip, prefijo='admin')
            if bloqueado:
                error = f'Demasiados intentos. Espera {bloqueado}s.'
                return render_template('admin_login.html', error=error)
            if request.form.get('password', '') == ADMIN_PASSWORD:
                session.clear()
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
        if not validar_csrf():
            return redirect(url_for('admin'))
        accion = request.form.get('accion')

        if accion == 'crear_colegio':
            nombre   = request.form.get('nombre', '').strip()
            slug     = request.form.get('slug', '').strip().lower().replace(' ', '-')
            num_p    = request.form.get('num_periodos', 4, type=int)
            venc     = request.form.get('vencimiento', '').strip() or None
            codigo   = request.form.get('codigo_registro', '').strip()
            pri_col  = request.form.get('primary_color', '#6c63ff').strip()
            sec_col  = request.form.get('secondary_color', '#3498db').strip()
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
                            ruta_logo = os.path.join(LOGO_FOLDER, logo_filename)
                            f.save(ruta_logo)
                            if not validar_imagen(ruta_logo):
                                os.remove(ruta_logo)
                                error = 'El archivo no es una imagen válida.'
                                logo_filename = ''
                if not error:
                    cm = conectar_master()
                    try:
                        cm.execute(
                            'INSERT INTO colegios (slug,nombre,logo,num_periodos,vencimiento,codigo_registro,codigo_profesores,codigo_directoras,codigo_rectores,primary_color,secondary_color) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                            (slug, nombre, logo_filename, num_p, venc, codigo, codigo, codigo, codigo, pri_col, sec_col))
                        cm.commit()
                    except sqlite3.IntegrityError:
                        error = f'El slug "{slug}" ya existe.'
                    finally:
                        cm.close()
                    if not error:
                            init_db(slug)
                            exito = f'Colegio "{nombre}" creado. URL: /{slug}/login · Código: {codigo}'
                            logger.info(f'Colegio creado: {slug}')

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
            pri_col = request.form.get('primary_color', '#6c63ff').strip()
            sec_col = request.form.get('secondary_color', '#3498db').strip()
            cm = conectar_master()
            cm.execute('UPDATE colegios SET nombre=?, num_periodos=?, vencimiento=?, codigo_registro=?, codigo_profesores=?, codigo_directoras=?, codigo_rectores=?, primary_color=?, secondary_color=? WHERE slug=?',
                       (nombre, num_p, venc, codigo, codigo, codigo, codigo, pri_col, sec_col, slug_e))
            cm.commit()
            if 'logo' in request.files:
                f = request.files['logo']
                if f and f.filename:
                    if not extension_permitida(f.filename):
                        error = 'Solo se permiten imágenes (png, jpg, jpeg, gif, webp).'
                    else:
                        ext = f.filename.rsplit('.', 1)[-1].lower()
                        logo_filename = f'{slug_e}.{ext}'
                        ruta_logo = os.path.join(LOGO_FOLDER, logo_filename)
                        f.save(ruta_logo)
                        if not validar_imagen(ruta_logo):
                            os.remove(ruta_logo)
                            error = 'El archivo no es una imagen válida.'
                        else:
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
    session.clear()
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
    ip = request.remote_addr

    if request.method == 'POST':
        if not validar_csrf():
            error = 'Error de seguridad. Intenta de nuevo.'
            paso = 1
        bloqueado = ip_bloqueada(ip, prefijo=f'recup_{slug}')
        if bloqueado:
            error = f'Demasiados intentos. Espera {bloqueado}s.'
            return render_template('recuperar.html', slug=slug, colegio=colegio, error=error, exito=exito, pregunta=pregunta, usuario_val=usuario_val, paso=paso)
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
                registrar_fallo(ip, prefijo=f'recup_{slug}')
            elif not prof['pregunta_secreta']:
                error = 'Este usuario no tiene pregunta secreta. Contacta al administrador.'
                registrar_fallo(ip, prefijo=f'recup_{slug}')
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
                registrar_fallo(ip, prefijo=f'recup_{slug}')
            elif prof['respuesta_secreta'].lower() != respuesta:
                error = 'Respuesta incorrecta.'
                pregunta = prof['pregunta_secreta']; paso = 2; conn.close()
                registrar_fallo(ip, prefijo=f'recup_{slug}')
            elif len(nueva) < 6:
                error = 'Mínimo 6 caracteres.'
                pregunta = prof['pregunta_secreta']; paso = 2; conn.close()
                registrar_fallo(ip, prefijo=f'recup_{slug}')
            elif nueva != confirmar:
                error = 'Las contraseñas no coinciden.'
                pregunta = prof['pregunta_secreta']; paso = 2; conn.close()
                registrar_fallo(ip, prefijo=f'recup_{slug}')
            else:
                conn.execute('UPDATE profesores SET password=? WHERE id=?',
                             (hash_pw(nueva), prof['id']))
                conn.commit(); conn.close()
                exito = '✅ Contraseña actualizada. Ya puedes ingresar.'
                limpiar_intentos(ip, prefijo=f'recup_{slug}')

    return render_template('recuperar.html',
                           slug=slug, colegio=colegio, error=error, exito=exito,
                           pregunta=pregunta, usuario_val=usuario_val, paso=paso)

# ── RECUPERAR CONTRASEÑA DIRECTORAS (AJAX) ────────────────────────────────────
@app.route('/<slug>/directora/buscar_usuario_recuperar', methods=['POST'])
def directora_buscar_usuario_recuperar(slug):
    if not validar_csrf(): return jsonify({'ok': False, 'mensaje': 'Error CSRF'})
    require_colegio(slug)
    ip = request.remote_addr
    usuario = request.form.get('usuario', '').strip()
    conn = conectar(slug)
    d = conn.execute(
        'SELECT * FROM directoras WHERE usuario=? AND activo=1', (usuario,)
    ).fetchone()
    conn.close()
    if not d:
        registrar_fallo(ip, prefijo=f'recup_directora_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Usuario no encontrado.'})
    if not d['pregunta_secreta']:
        registrar_fallo(ip, prefijo=f'recup_directora_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Este usuario no tiene pregunta secreta. Contacta al administrador.'})
    return jsonify({'ok': True, 'pregunta': d['pregunta_secreta']})

@app.route('/<slug>/directora/cambiar_password_recuperar', methods=['POST'])
def directora_cambiar_password_recuperar(slug):
    if not validar_csrf(): return jsonify({'ok': False, 'mensaje': 'Error CSRF'})
    require_colegio(slug)
    ip = request.remote_addr
    usuario   = request.form.get('usuario', '').strip()
    respuesta = request.form.get('respuesta', '').strip().lower()
    nueva     = request.form.get('nueva', '').strip()
    conn = conectar(slug)
    d = conn.execute(
        'SELECT * FROM directoras WHERE usuario=? AND activo=1', (usuario,)
    ).fetchone()
    if not d:
        conn.close(); registrar_fallo(ip, prefijo=f'recup_directora_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Usuario no encontrado.'})
    if not d['respuesta_secreta'] or d['respuesta_secreta'].lower() != respuesta:
        conn.close(); registrar_fallo(ip, prefijo=f'recup_directora_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Respuesta incorrecta.'})
    if len(nueva) < 6:
        conn.close(); registrar_fallo(ip, prefijo=f'recup_directora_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Mínimo 6 caracteres.'})
    conn.execute('UPDATE directoras SET password=? WHERE id=?', (hash_pw(nueva), d['id']))
    conn.commit(); conn.close()
    limpiar_intentos(ip, prefijo=f'recup_directora_{slug}')
    return jsonify({'ok': True, 'mensaje': 'Contraseña actualizada. Ya puedes ingresar.'})

# ── LOGIN ─────────────────────────────────────────────────────────────────────
@app.route('/<slug>/login', methods=['GET', 'POST'])
def login(slug):
    require_colegio(slug)
    init_db(slug)
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
                prof = conn.execute('SELECT * FROM profesores WHERE usuario=? AND activo=1', (u,)).fetchone()
                if prof and verificar_pw(p, prof['password']):
                    if necesita_rehash(prof['password']):
                        conn.execute('UPDATE profesores SET password=? WHERE id=?',
                                     (hash_pw(p), prof['id']))
                        conn.commit()
                        logger.info(f'Hash migrado para profesor id={prof["id"]} en {slug}')
                    conn.close()
                    session.clear()
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
            # Validar código POR COLEGIO Y ROL
            codigo_colegio = get_codigo_registro(slug, 'profesores')
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
                            except Exception: pass
                    conn.commit(); conn.close()
                    error = '✅ Registro exitoso. Ya puedes ingresar.'

        elif accion == 'estudiante':
            nombre     = request.form.get('nombre_est', '').strip().lower()
            jornada    = request.form.get('jornada_est', '').strip()
            pin_ingresado = request.form.get('pin_est', '').strip()
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
                if alumno['pin'] and pin_ingresado != alumno['pin']:
                    error = 'PIN incorrecto.'
                else:
                    session.clear()
                    session.permanent = True
                    session[f'rol_{slug}']       = 'estudiante'
                    session[f'alumno_id_{slug}'] = alumno['id']
                    return redirect(url_for('vista_estudiante', slug=slug))
            else:
                error = 'No se encontró ese estudiante.'

        elif accion == 'directora_login':
            u = request.form.get('dir_usuario', '').strip()
            p = request.form.get('dir_password', '').strip()
            conn = conectar(slug)
            d = conn.execute(
                'SELECT * FROM directoras WHERE usuario=? AND activo=1', (u,)).fetchone()
            conn.close()
            if d and verificar_pw(p, d['password']):
                session.clear()
                session.permanent = True
                session[f'directora_id_{slug}'] = d['id']
                return redirect(url_for('directora_panel', slug=slug))
            error = 'Usuario o contraseña incorrectos.'

        elif accion == 'rector_login':
            u = request.form.get('rec_usuario', '').strip()
            p = request.form.get('rec_password', '').strip()
            conn = conectar(slug)
            rector = conn.execute(
                'SELECT * FROM rectores WHERE usuario=? AND activo=1', (u,)).fetchone()
            conn.close()
            if rector and verificar_pw(p, rector['password']):
                session.clear()
                session.permanent = True
                session[f'rector_id_{slug}'] = rector['id']
                return redirect(url_for('rector_panel', slug=slug))
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
        if not validar_csrf(): return ('Error CSRF', 403)
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
    session.clear()
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
    try:
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
        # Pre-fetch grade data for all students (avoids N+1 queries)
        aid_list = [a['id'] for a in alumnos]
        if aid_list:
            placeholders = ','.join('?' * len(aid_list))
            notas_all = conn.execute(
                f'''SELECT n.aid, n.actividad_id, n.val, n.id FROM notas n
                    JOIN actividades ac ON ac.id=n.actividad_id
                    WHERE n.aid IN ({placeholders}) AND ac.materia=? AND ac.jornada=? AND ac.curso=?
                    AND COALESCE(ac.periodo,1)=? ORDER BY n.aid''',
                (*aid_list, materia, jornada, curso_sel, periodo_sel)).fetchall()
            notas_by_aid = {}
            for r in notas_all:
                notas_by_aid.setdefault(r['aid'], []).append(r)
            evals_all = conn.execute(
                f'''SELECT aid, evaluacion, autoevaluacion FROM evaluaciones
                    WHERE aid IN ({placeholders}) AND profesor_id=? AND materia=? AND jornada=?
                    AND COALESCE(periodo,1)=?''',
                (*aid_list, prof['id'], materia, jornada, periodo_sel)).fetchall()
            evals_by_aid = {r['aid']: r for r in evals_all}
        else:
            notas_by_aid = {}
            evals_by_aid = {}
        # Batch-fetch asistencia and observaciones to avoid N+1 queries
        asis_all = {}
        asis_ultimo = {}
        obs_all = {}
        if aid_list:
            rows_asistencia = conn.execute(
                f'SELECT aid, fecha, estado FROM asistencia WHERE aid IN ({placeholders}) ORDER BY aid, fecha',
                aid_list).fetchall()
            for r in rows_asistencia:
                asis_all.setdefault(r['aid'], []).append(r)
            rows_ultimo = conn.execute(
                f'SELECT aid, estado FROM asistencia WHERE id IN (SELECT MAX(id) FROM asistencia WHERE aid IN ({placeholders}) GROUP BY aid)',
                aid_list).fetchall() if rows_asistencia else []
            asis_ultimo = {r['aid']: r['estado'] for r in rows_ultimo}
            rows_obs = conn.execute(
                f'SELECT id, aid, materia, texto, fecha FROM observaciones WHERE aid IN ({placeholders}) AND materia=? ORDER BY aid, fecha DESC',
                (*aid_list, materia)).fetchall()
            for r in rows_obs:
                obs_all.setdefault(r['aid'], []).append(r)
        for a in alumnos:
            notas_raw = notas_by_aid.get(a['id'], [])
            notas_map = {nr['actividad_id']: {'val': nr['val'], 'id': nr['id']} for nr in notas_raw}
            ev = evals_by_aid.get(a['id'])
            eval_v = ev['evaluacion']     if ev and ev['evaluacion']     is not None else None
            auto_v = ev['autoevaluacion'] if ev and ev['autoevaluacion'] is not None else None
            todas = [nr['val'] for nr in notas_raw]
            if eval_v is not None: todas.append(eval_v)
            if auto_v is not None: todas.append(auto_v)
            prom = round(sum(todas) / len(todas), 2) if todas else None
            historial_raw = asis_all.get(a['id'], [])
            hist_meses = {}
            for h in historial_raw:
                if h['fecha']:
                    p2 = h['fecha'].split('-')
                    if len(p2) >= 2:
                        label = f"{MESES.get(p2[1], p2[1])} {p2[0]}"
                        hist_meses.setdefault(label, []).append({'fecha': h['fecha'], 'estado': h['estado']})
            ult_estado = asis_ultimo.get(a['id'])
            obs = obs_all.get(a['id'], [])
            datos.append({
                'id': a['id'], 'num_curso': a['num_curso'],
                'nombre': a['nombre'], 'curso': a['curso'],
                'promedio': prom, 'notas_map': notas_map,
                'evaluacion':     eval_v if eval_v is not None else '',
                'autoevaluacion': auto_v if auto_v is not None else '',
                'asistencia': ult_estado or '-',
                'historial_meses': hist_meses,
                'observaciones': [dict(o) for o in obs],
            })

        promedios = [d['promedio'] for d in datos if d['promedio'] is not None]
        prom_gral = round(sum(promedios) / len(promedios), 2) if promedios else None
        mejor     = max(datos, key=lambda x: x['promedio'] or 0, default={'nombre': 'N/A', 'promedio': None})

        # ── Dashboard data ──────────────────────────────────────────────────
        DIAS = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
        hoy_idx = datetime.today().weekday()
        hoy_nombre = DIAS[hoy_idx] if hoy_idx < 7 else ''
        hoy_fecha = datetime.today().strftime('%Y-%m-%d')
        total_alumnos = sum(
            conn.execute(
                'SELECT COUNT(*) as c FROM alumnos WHERE curso=? AND jornada=? AND activo=1',
                (c, jornada)
            ).fetchone()['c'] for c in mis_cursos
        ) if mis_cursos else 0
        horario_hoy = conn.execute(
            'SELECT * FROM horarios_curso WHERE materia=? AND jornada=? AND dia=? ORDER BY franja',
            (materia, jornada, hoy_nombre)
        ).fetchall() if curso_sel else []
        asis_hoy = conn.execute(
            "SELECT COUNT(DISTINCT aid) as total FROM asistencia WHERE fecha=?",
            (hoy_fecha,)
        ).fetchone()
        asistencia_hoy = asis_hoy['total'] if asis_hoy else 0
        notas_pend = 0
        if curso_sel and actividades:
            for act in actividades:
                count = conn.execute(
                    'SELECT COUNT(*) as c FROM alumnos WHERE curso=? AND jornada=? AND activo=1 AND id NOT IN (SELECT aid FROM notas WHERE actividad_id=?)',
                    (curso_sel, jornada, act['id'])
                ).fetchone()
                notas_pend += count['c'] if count else 0
        alertas = []
        if curso_sel:
            rows = conn.execute(
                "SELECT a.nombre, a.id, COUNT(*) as faltas FROM asistencia asis JOIN alumnos a ON a.id=asis.aid WHERE asis.estado='A' AND a.curso=? AND a.jornada=? AND a.activo=1 GROUP BY asis.aid HAVING faltas > 1 ORDER BY faltas DESC LIMIT 5",
                (curso_sel, jornada)
            ).fetchall()
            for r in rows: alertas.append({'nombre': r['nombre'], 'faltas': r['faltas']})
            for e in datos:
                if e['promedio'] is not None and e['promedio'] < 3.0:
                    alertas.append({'nombre': e['nombre'], 'promedio': e['promedio']})
            alertas = alertas[:5]
        pendientes = comunicaciones_pendientes(slug, 'profesor', prof['id'])
        num_periodos = int(colegio['num_periodos']) if colegio and colegio['num_periodos'] else 4
        pc = periodo_cerrado(slug, periodo_sel) if curso_sel and materia else False
        solicitudes_pend = conn.execute(
            'SELECT COUNT(*) as c FROM solicitudes_modificacion WHERE solicitado_por=? AND estado=?',
            (prof['id'], 'pendiente')).fetchone()['c'] if curso_sel else 0
    finally:
        conn.close()
    return render_template('index.html',
                           profesor=prof, mis_cursos=mis_cursos, curso_sel=curso_sel,
                           estudiantes=datos, actividades=actividades, compromisos=agenda,
                           prom_general=prom_gral, mejor=mejor, slug=slug, colegio=colegio,
                           num_periodos=num_periodos, periodo_sel=periodo_sel,
                           materia=materia, jornada=jornada,
                           materias_jornadas=get_materias_profesor(slug, prof['id']),
                           hoy_nombre=hoy_nombre, hoy_fecha=hoy_fecha,
                           total_alumnos=total_alumnos, horario_hoy=horario_hoy,
                           asistencia_hoy=asistencia_hoy, notas_pend=notas_pend,
                            alertas=alertas,
                            periodo_cerrado=pc,
                            solicitudes_pendientes_mod=solicitudes_pend,
                            comunicaciones_pendientes=pendientes)

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

@app.route('/<slug>/borrar_actividad/<int:act_id>', methods=['POST'])
def borrar_actividad(slug, act_id):
    if not validar_csrf(): return redirect(url_for('home', slug=slug))
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
    act = conn.execute(
        'SELECT a.id, a.profesor_id, a.curso, COALESCE(a.periodo,1) as p FROM actividades a WHERE a.id=?',
        (actividad_id,)).fetchone()
    if not act:
        conn.close()
        return ('', 404)
    if act['profesor_id'] != prof['id']:
        conn.close()
        return ('', 403)
    alumno = conn.execute('SELECT id FROM alumnos WHERE id=? AND curso=? AND activo=1',
                          (aid, act['curso'])).fetchone()
    if not alumno:
        conn.close()
        return ('', 403)
    if periodo_cerrado(slug, act['p'], conn):
        conn.close()
        return ('Periodo cerrado', 423)
    old = conn.execute(
        'SELECT val FROM notas WHERE aid=? AND actividad_id=?',
        (aid, actividad_id)).fetchone()
    old_val = old['val'] if old else None
    conn.execute(
        '''INSERT INTO notas (aid,actividad_id,val) VALUES (?,?,?)
           ON CONFLICT(aid,actividad_id) DO UPDATE SET val=excluded.val''',
        (aid, actividad_id, val))
    conn.commit()
    audit_log(slug, prof['id'], 'nota_editada', 'notas', registro_id=None,
              valor_anterior={'aid': aid, 'actividad_id': actividad_id, 'val': old_val},
              valor_nuevo={'aid': aid, 'actividad_id': actividad_id, 'val': val})
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
    if periodo_cerrado(slug, periodo, conn):
        conn.close()
        return ('Periodo cerrado', 423)
    existing = conn.execute(
        '''SELECT evaluacion, autoevaluacion FROM evaluaciones
           WHERE aid=? AND profesor_id=? AND materia=? AND jornada=? AND COALESCE(periodo,1)=?''',
        (aid, prof['id'], materia, jornada, periodo)
    ).fetchone()
    old_eval = existing['evaluacion'] if existing else None
    old_auto = existing['autoevaluacion'] if existing else None
    ev_final = ev if ev is not None else old_eval
    au_final = au if au is not None else old_auto
    conn.execute(
        '''INSERT INTO evaluaciones
           (aid,profesor_id,materia,jornada,evaluacion,autoevaluacion,periodo)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(aid,profesor_id,materia,jornada,periodo)
           DO UPDATE SET evaluacion=excluded.evaluacion, autoevaluacion=excluded.autoevaluacion''',
        (aid, prof['id'], materia, jornada, ev_final, au_final, periodo))
    conn.commit()
    audit_log(slug, prof['id'], 'evaluacion_editada', 'evaluaciones', registro_id=None,
              valor_anterior={'aid': aid, 'evaluacion': old_eval, 'autoevaluacion': old_auto},
              valor_nuevo={'aid': aid, 'evaluacion': ev_final, 'autoevaluacion': au_final})
    conn.close()
    return ('', 204)

# ── SOLICITUDES DE MODIFICACION ──────────────────────────────────────────────
@app.route('/<slug>/solicitar_modificacion', methods=['POST'])
def solicitar_modificacion(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return ('', 403)
    if not validar_csrf(): return ('Error CSRF', 403)
    aid              = request.form.get('alumno_id', request.form.get('aid'), type=int)
    actividad_id     = request.form.get('actividad_id', type=int)
    nombre_actividad = request.form.get('nombre_actividad', '').strip()
    periodo          = request.form.get('periodo', type=int)
    nota_actual_raw  = request.form.get('nota_actual', '').strip()
    nota_solicitada  = request.form.get('nota_solicitada', type=float)
    motivo           = request.form.get('motivo', '').strip()
    if None in (aid, nota_solicitada) or not motivo:
        return ('Datos incompletos', 400)
    if periodo is None:
        periodo = 1
    conn = conectar(slug)
    campo = 'nota'
    jornada_ctx, materia_ctx = get_sesion_jornada_materia(slug)
    materia = materia_ctx or ''
    nota_actual_val = None
    if actividad_id is not None:
        act = conn.execute(
            'SELECT a.id, a.nombre, a.materia, COALESCE(a.periodo,1) as p FROM actividades a WHERE a.id=?',
            (actividad_id,)).fetchone()
        if not act:
            conn.close()
            return ('Actividad no encontrada', 404)
        materia = act['materia']
        nota_db = conn.execute(
            'SELECT val FROM notas WHERE aid=? AND actividad_id=?',
            (aid, actividad_id)).fetchone()
        nota_actual_val = nota_db['val'] if nota_db else None
    else:
        if nombre_actividad == 'Evaluación':
            campo = 'evaluacion'
            alumno = conn.execute(
                'SELECT evaluacion FROM evaluaciones WHERE aid=? AND profesor_id=? AND materia=? AND COALESCE(periodo,1)=?',
                (aid, prof['id'], materia, periodo)).fetchone()
            nota_actual_val = alumno['evaluacion'] if alumno else None
        elif nombre_actividad == 'Autoevaluación':
            campo = 'autoevaluacion'
            alumno = conn.execute(
                'SELECT autoevaluacion FROM evaluaciones WHERE aid=? AND profesor_id=? AND materia=? AND COALESCE(periodo,1)=?',
                (aid, prof['id'], materia, periodo)).fetchone()
            nota_actual_val = alumno['autoevaluacion'] if alumno else None
        else:
            conn.close()
            return ('Actividad no especificada', 400)
    conn.execute(
        '''INSERT INTO solicitudes_modificacion
           (periodo, aid, actividad_id, campo, materia, nota_actual, nota_solicitada, motivo, solicitado_por)
           VALUES (?,?,?,?,?,?,?,?,?)''',
        (periodo, aid, actividad_id, campo, materia,
         nota_actual_val, nota_solicitada, motivo, prof['id']))
    conn.commit()
    audit_log(slug, prof['id'], 'solicitud_creada', 'solicitudes_modificacion',
              valor_anterior={'aid': aid, 'actividad_id': actividad_id, 'campo': campo, 'val': nota_actual_val},
              valor_nuevo={'aid': aid, 'actividad_id': actividad_id, 'campo': campo, 'val': nota_solicitada,
                           'motivo': motivo})
    conn.close()
    return redirect(url_for('home', slug=slug))

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

@app.route('/<slug>/borrar_trabajo/<int:id_t>', methods=['POST'])
def borrar_trabajo(slug, id_t):
    if not validar_csrf(): return redirect(url_for('home', slug=slug))
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
        audit_log(slug, prof['id'], 'crear', 'alumnos')
        conn.close()
    return redirect(url_for('home', slug=slug, curso=curso_sel))

@app.route('/<slug>/archivar_alumno/<int:id>', methods=['POST'])
def archivar_alumno(slug, id):
    if not validar_csrf(): return redirect(url_for('home', slug=slug))
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    curso_sel = request.form.get('curso', '')
    conn = conectar(slug)
    conn.execute('UPDATE alumnos SET activo=0 WHERE id=?', (id,))
    conn.commit(); audit_log(slug, prof['id'], 'archivar', 'alumnos', id)
    conn.close()
    return redirect(url_for('home', slug=slug, curso=curso_sel))

@app.route('/<slug>/reactivar_alumno/<int:id>', methods=['POST'])
def reactivar_alumno(slug, id):
    if not validar_csrf(): return redirect(url_for('archivados', slug=slug))
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    curso_sel = request.form.get('curso', '')
    conn = conectar(slug)
    conn.execute('UPDATE alumnos SET activo=1 WHERE id=?', (id,))
    conn.commit(); audit_log(slug, prof['id'], 'reactivar', 'alumnos', id)
    conn.close()
    return redirect(url_for('archivados', slug=slug, curso=curso_sel))

@app.route('/<slug>/eliminar_alumno/<int:id>', methods=['POST'])
def eliminar_alumno(slug, id):
    if not validar_csrf(): return redirect(url_for('archivados', slug=slug))
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return redirect(url_for('login', slug=slug))
    curso_sel = request.form.get('curso', '')
    conn = conectar(slug)
    conn.execute('DELETE FROM alumnos WHERE id=?', (id,))
    conn.execute('DELETE FROM notas WHERE aid=?', (id,))
    conn.execute('DELETE FROM evaluaciones WHERE aid=?', (id,))
    conn.execute('DELETE FROM asistencia WHERE aid=?', (id,))
    conn.execute('DELETE FROM observaciones WHERE aid=?', (id,))
    conn.commit(); audit_log(slug, prof['id'], 'eliminar', 'alumnos', id)
    conn.close()
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

@app.route('/<slug>/archivar_profesor/<int:id>', methods=['POST'])
def archivar_profesor(slug, id):
    if not validar_csrf(): return jsonify({'ok': False, 'mensaje': 'Error CSRF'}), 403
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return jsonify({'ok': False, 'mensaje': 'No autorizado'}), 403
    conn = conectar(slug)
    conn.execute('UPDATE profesores SET activo=0 WHERE id=?', (id,))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

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
        return jsonify({'ok': False, 'mensaje': 'Error al archivar. Intenta de nuevo.'})
    finally:
        conn.close()

@app.route('/<slug>/reactivar_profesor/<int:id>', methods=['POST'])
def reactivar_profesor(slug, id):
    if not validar_csrf(): return jsonify({'ok': False, 'mensaje': 'Error CSRF'}), 403
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return jsonify({'ok': False, 'mensaje': 'No autorizado'}), 403
    conn = conectar(slug)
    conn.execute('UPDATE profesores SET activo=1 WHERE id=?', (id,))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/<slug>/eliminar_profesor/<int:id>', methods=['POST'])
def eliminar_profesor(slug, id):
    if not validar_csrf(): return jsonify({'ok': False, 'mensaje': 'Error CSRF'}), 403
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return jsonify({'ok': False, 'mensaje': 'No autorizado'}), 403
    conn = conectar(slug)
    conn.execute('DELETE FROM profesores WHERE id=?', (id,))
    conn.execute('DELETE FROM asignaciones_materia WHERE profesor_id=?', (id,))
    conn.execute('DELETE FROM asignaciones_curso WHERE profesor_id=?', (id,))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

# ── ASISTENCIA ────────────────────────────────────────────────────────────────
@app.route('/<slug>/marcar_asistencia', methods=['POST'])
def marcar_asistencia(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if not prof: return ('', 403)
    if not validar_csrf(): return ('Error CSRF', 403)
    aid    = request.form.get('aid', type=int)
    estado = request.form.get('estado')
    if aid is None or not estado: return ('', 400)
    jornada, materia = get_sesion_jornada_materia(slug)
    conn = conectar(slug)
    cursos_prof = get_cursos_profesor(slug, prof['id'], materia, jornada)
    if not cursos_prof:
        conn.close(); return ('', 403)
    alumno = conn.execute(
        'SELECT id FROM alumnos WHERE id=? AND curso IN ({}) AND jornada=? AND activo=1'.format(
            ','.join('?' * len(cursos_prof))),
        (aid, *cursos_prof, jornada)).fetchone()
    if not alumno:
        conn.close(); return ('', 403)
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
    aid   = request.form.get('aid', type=int)
    if not texto or aid is None: return ('', 400)
    conn = conectar(slug)
    cursos_prof = get_cursos_profesor(slug, prof['id'], materia, jornada)
    if not cursos_prof:
        conn.close(); return ('', 403)
    alumno = conn.execute(
        'SELECT id FROM alumnos WHERE id=? AND curso IN ({}) AND jornada=? AND activo=1'.format(
            ','.join('?' * len(cursos_prof))),
        (aid, *cursos_prof, jornada)).fetchone()
    if not alumno:
        conn.close(); return ('', 403)
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
    if not validar_csrf():
        return 'Error de seguridad', 400
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

@app.route('/<slug>/quitar_curso/<curso>', methods=['POST'])
def quitar_curso(slug, curso):
    if not validar_csrf(): return redirect(url_for('cambiar_password', slug=slug))
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
    if prof and (not jornada or not materia):
        return redirect(url_for('seleccionar_jornada', slug=slug))
    mis_cursos = get_cursos_profesor(slug, prof['id'], materia, jornada) if prof else []
    curso_sel  = request.args.get('curso', mis_cursos[0] if mis_cursos else None)

    if request.method == 'POST':
        if not validar_csrf():
            return redirect(url_for('horarios', slug=slug))
        c = conectar(slug)
        try:
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
            c.commit()
        finally:
            c.close()
        return ('', 204)
    c = conectar(slug)
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
    periodo = request.args.get('periodo', 1, type=int)
    notas_raw = conn.execute(
        '''SELECT ac.materia, ac.nombre as act_nombre, n.val
           FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
           WHERE n.aid=? AND ac.curso=? AND ac.jornada=?
           AND COALESCE(ac.periodo,1)=?
           ORDER BY ac.materia, ac.orden''',
        (aid, alumno['curso'], alumno['jornada'], periodo)).fetchall()
    evals_raw = conn.execute(
        'SELECT materia, evaluacion, autoevaluacion FROM evaluaciones WHERE aid=? AND COALESCE(periodo,1)=?',
        (aid, periodo)).fetchall()
    evals_map = {e['materia']: dict(e) for e in evals_raw}
    notas_pm = {}
    for nr in notas_raw:
        notas_pm.setdefault(nr['materia'], []).append({'actividad': nr['act_nombre'], 'val': nr['val']})
    for mat in evals_map:
        if mat not in notas_pm: notas_pm[mat] = []
    proms_pm = {}
    todos_finales = []
    for mat, notas in notas_pm.items():
        notas_vals = [n['val'] for n in notas]
        act_prom = round(sum(notas_vals) / len(notas_vals), 2) if notas_vals else None
        ev = evals_map.get(mat, {})
        eval_v = ev.get('evaluacion') if ev.get('evaluacion') is not None else None
        auto_v = ev.get('autoevaluacion') if ev.get('autoevaluacion') is not None else None
        if act_prom is not None or eval_v is not None or auto_v is not None:
            total_peso = 0; nota_final = 0
            if act_prom is not None: nota_final += act_prom * 0.65; total_peso += 0.65
            if eval_v   is not None: nota_final += eval_v   * 0.25; total_peso += 0.25
            if auto_v   is not None: nota_final += auto_v   * 0.10; total_peso += 0.10
            prom = round(nota_final / total_peso, 2) if total_peso else None
        else:
            prom = None
        proms_pm[mat] = prom
        if prom is not None: todos_finales.append(prom)
    promedio_general = round(sum(todos_finales) / len(todos_finales), 2) if todos_finales else None
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
    pendientes = comunicaciones_pendientes(slug, 'estudiante', aid)
    return render_template('estudiante.html',
                           alumno=alumno, slug=slug, colegio=colegio, agenda=agenda,
                           notas_por_materia=notas_pm, evals_map=evals_map,
                           proms_por_materia=proms_pm,
                           promedio_general=promedio_general,
                           asist_stats=asist_stats, historial_meses=historial_meses,
                           observaciones=observaciones, horario_map=horario_map,
                           comunicaciones_pendientes=pendientes)

# ── DIRECTORA ─────────────────────────────────────────────────────────────────
def get_directora(slug):
    did = session.get(f'directora_id_{slug}')
    if not did: return None
    conn = conectar(slug)
    d = conn.execute('SELECT * FROM directoras WHERE id=? AND activo=1', (did,)).fetchone()
    conn.close()
    if not d:
        session.pop(f'directora_id_{slug}', None)
    return d

def get_rector(slug):
    rid = session.get(f'rector_id_{slug}')
    if not rid: return None
    conn = conectar(slug)
    r = conn.execute('SELECT * FROM rectores WHERE id=? AND activo=1', (rid,)).fetchone()
    conn.close()
    if not r:
        session.pop(f'rector_id_{slug}', None)
    return r

@app.route('/<slug>/rector/login', methods=['GET', 'POST'])
def rector_login(slug):
    require_colegio(slug)
    init_db(slug)
    colegio = get_colegio(slug)
    error = exito = None
    ip = request.remote_addr
    if request.method == 'POST':
        if not validar_csrf():
            error = 'Error de seguridad.'
            return render_template('rector_login.html', slug=slug, colegio=colegio, error=error, exito=exito)
        bloqueado = ip_bloqueada(ip, prefijo=f'rector_{slug}')
        if bloqueado:
            error = f'Demasiados intentos. Espera {bloqueado}s.'
            return render_template('rector_login.html', slug=slug, colegio=colegio, error=error, exito=exito)
        u = request.form.get('usuario', '').strip()
        p = request.form.get('password', '').strip()
        conn = conectar(slug)
        rector = conn.execute(
            'SELECT * FROM rectores WHERE usuario=? AND activo=1', (u,)).fetchone()
        conn.close()
        if rector and verificar_pw(p, rector['password']):
            session.clear()
            session.permanent = True
            session[f'rector_id_{slug}'] = rector['id']
            limpiar_intentos(ip, prefijo=f'rector_{slug}')
            return redirect(url_for('rector_panel', slug=slug))
        registrar_fallo(ip, prefijo=f'rector_{slug}')
        error = 'Usuario o contraseña incorrectos.'
    return render_template('rector_login.html', slug=slug, colegio=colegio,
                           error=error, exito=exito)

@app.route('/<slug>/rector/registrar', methods=['POST'])
def rector_registrar(slug):
    if not validar_csrf():
        return 'Error de seguridad', 400
    require_colegio(slug)
    init_db(slug)
    colegio  = get_colegio(slug)
    error = exito = None
    nombre   = request.form.get('nombre', '').strip()
    usuario  = request.form.get('usuario', '').strip()
    pw       = request.form.get('password', '').strip()
    confirm  = request.form.get('confirmar_password', '').strip()
    jornada  = request.form.get('jornada', '').strip()
    email    = request.form.get('email', '').strip()
    pregunta = request.form.get('pregunta_secreta', '').strip()
    resp     = request.form.get('respuesta_secreta', '').strip().lower()
    codigo   = request.form.get('codigo_registro_rec', '').strip()

    codigo_colegio = get_codigo_registro(slug, 'rectores')
    if codigo_colegio and codigo != codigo_colegio:
        error = 'Código de invitación incorrecto.'
    elif pw != confirm:
        error = 'Las contraseñas no coinciden.'
    elif not nombre or not usuario or not pw or not jornada:
        error = 'Completa todos los campos obligatorios.'
    elif len(pw) < 6:
        error = 'Mínimo 6 caracteres.'
    elif not pregunta or not resp:
        error = 'Debes elegir una pregunta secreta y escribir tu respuesta.'
    else:
        conn = conectar(slug)
        if conn.execute('SELECT 1 FROM rectores WHERE usuario=?', (usuario,)).fetchone():
            error = 'Ese usuario ya existe. Elige otro nombre de usuario.'
            conn.close()
        else:
            conn.execute(
                '''INSERT INTO rectores
                   (nombre, usuario, password, jornada, email, pregunta_secreta, respuesta_secreta)
                   VALUES (?,?,?,?,?,?,?)''',
                (nombre, usuario, hash_pw(pw), jornada, email, pregunta, resp))
            conn.commit()
            conn.close()
            exito = 'Cuenta de Rector creada. Ya puedes ingresar.'
    return render_template('rector_login.html', slug=slug, colegio=colegio,
                           error=error, exito=exito)

@app.route('/<slug>/rector/buscar_usuario_recuperar', methods=['POST'])
def rector_buscar_usuario_recuperar(slug):
    if not validar_csrf(): return jsonify({'ok': False, 'mensaje': 'Error CSRF'})
    require_colegio(slug)
    ip = request.remote_addr
    u = request.form.get('usuario', '').strip()
    conn = conectar(slug)
    r = conn.execute('SELECT pregunta_secreta FROM rectores WHERE usuario=? AND activo=1', (u,)).fetchone()
    conn.close()
    if not r or not r['pregunta_secreta']:
        registrar_fallo(ip, prefijo=f'recup_rector_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Usuario no encontrado.'})
    return jsonify({'ok': True, 'pregunta': r['pregunta_secreta']})

@app.route('/<slug>/rector/cambiar_password_recuperar', methods=['POST'])
def rector_cambiar_password_recuperar(slug):
    if not validar_csrf(): return jsonify({'ok': False, 'mensaje': 'Error CSRF'})
    require_colegio(slug)
    ip = request.remote_addr
    u = request.form.get('usuario', '').strip()
    rta = request.form.get('respuesta', '').strip().lower()
    nueva = request.form.get('nueva', '').strip()
    conn = conectar(slug)
    r = conn.execute('SELECT * FROM rectores WHERE usuario=? AND activo=1', (u,)).fetchone()
    if not r:
        conn.close(); registrar_fallo(ip, prefijo=f'recup_rector_{slug}'); return jsonify({'ok': False, 'mensaje': 'Usuario no encontrado.'})
    if not r['respuesta_secreta'] or r['respuesta_secreta'].lower() != rta:
        conn.close(); registrar_fallo(ip, prefijo=f'recup_rector_{slug}'); return jsonify({'ok': False, 'mensaje': 'Respuesta incorrecta.'})
    if len(nueva) < 6:
        conn.close(); registrar_fallo(ip, prefijo=f'recup_rector_{slug}'); return jsonify({'ok': False, 'mensaje': 'Mínimo 6 caracteres.'})
    conn.execute('UPDATE rectores SET password=? WHERE id=?', (hash_pw(nueva), r['id']))
    conn.commit(); conn.close()
    limpiar_intentos(ip, prefijo=f'recup_rector_{slug}')
    return jsonify({'ok': True, 'mensaje': 'Contraseña actualizada. Ya puedes ingresar.'})

@app.route('/<slug>/rector')
@app.route('/<slug>/rector/panel')
def rector_panel(slug):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    colegio = get_colegio(slug)
    conn = conectar(slug)
    total_est = conn.execute(
        'SELECT COUNT(*) as c FROM alumnos WHERE activo=1').fetchone()['c']
    total_prof = conn.execute(
        'SELECT COUNT(*) as c FROM profesores WHERE activo=1').fetchone()['c']
    total_cursos = conn.execute(
        'SELECT COUNT(DISTINCT curso) as c FROM alumnos WHERE activo=1').fetchone()['c']
    total_materias = conn.execute(
        'SELECT COUNT(DISTINCT materia) as c FROM asignaciones_materia').fetchone()['c']
    total_directoras = conn.execute(
        'SELECT COUNT(*) as c FROM directoras WHERE activo=1').fetchone()['c']
    hoy = datetime.today().strftime('%Y-%m-%d')
    asistencia_hoy = conn.execute(
        "SELECT COUNT(DISTINCT aid) as c FROM asistencia WHERE fecha=?", (hoy,)).fetchone()['c']
    comunicaciones = conn.execute(
        '''SELECT * FROM comunicaciones WHERE rector_id=? AND activo=1
           ORDER BY fecha_creacion DESC LIMIT 5''',
        (rector['id'],)).fetchall()
    notif_count = conn.execute(
        'SELECT COUNT(*) as c FROM notificaciones WHERE usuario_tipo=? AND usuario_id=? AND leida=0',
        ('rector', rector['id'])).fetchone()['c']
    conn.close()
    prom_general = 0
    return render_template('rector_panel.html',
                           slug=slug, colegio=colegio, rector=rector,
                           total_estudiantes=total_est,
                           total_profesores=total_prof,
                           total_cursos=total_cursos,
                           total_materias=total_materias,
                           total_directoras=total_directoras,
                           asistencia_hoy=asistencia_hoy,
                           comunicaciones=comunicaciones,
                           notif_count=notif_count)

@app.route('/<slug>/rector/logout')
def rector_logout(slug):
    session.clear()
    return redirect(url_for('login', slug=slug))

# ── RECTOR: HORARIOS ───────────────────────────────────────────────────────────
@app.route('/<slug>/rector/horarios')
def rector_horarios(slug):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    colegio = get_colegio(slug)
    conn = conectar(slug)
    cursos = [r['curso'] for r in conn.execute(
        'SELECT DISTINCT curso FROM alumnos WHERE activo=1 ORDER BY curso').fetchall()]
    jornadas = JORNADAS
    conn.close()
    return render_template('rector_horarios.html',
                           slug=slug, colegio=colegio, rector=rector,
                           cursos=cursos, jornadas=jornadas,
                           notif_count=notificaciones_no_leidas(slug, 'rector', rector['id']))

@app.route('/<slug>/rector/horarios/datos')
def rector_horarios_datos(slug):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return jsonify({})
    curso = request.args.get('curso', '')
    jornada = request.args.get('jornada', '')
    if not curso: return jsonify({})
    conn = conectar(slug)
    filas = conn.execute(
        'SELECT dia, franja, num, materia, profesor FROM horarios_curso WHERE curso=? AND jornada=?',
        (curso, jornada)).fetchall()
    conn.close()
    mapa = {}
    for r in filas:
        mapa[f"{r['dia']}_{r['franja']}"] = {'num': r['num'], 'materia': r['materia'], 'profesor': r['profesor']}
    return jsonify(mapa)

# ── RECTOR: PROFESORES ─────────────────────────────────────────────────────────
@app.route('/<slug>/rector/profesores')
def rector_profesores(slug):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    colegio = get_colegio(slug)
    conn = conectar(slug)
    profesores = [dict(r) for r in conn.execute(
        'SELECT id, nombre, email, activo FROM profesores ORDER BY nombre').fetchall()]
    conn.close()
    return render_template('rector_profesores.html',
                           slug=slug, colegio=colegio, rector=rector,
                           profesores=profesores,
                           notif_count=notificaciones_no_leidas(slug, 'rector', rector['id']))

# ── RECTOR: ESTUDIANTES ────────────────────────────────────────────────────────
@app.route('/<slug>/rector/estudiantes')
def rector_estudiantes(slug):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    colegio = get_colegio(slug)
    conn = conectar(slug)
    estudiantes = [dict(r) for r in conn.execute(
        '''SELECT id, nombre, curso, jornada, activo FROM alumnos WHERE activo=1
           ORDER BY curso, nombre''').fetchall()]
    conn.close()
    return render_template('rector_estudiantes.html',
                           slug=slug, colegio=colegio, rector=rector,
                           estudiantes=estudiantes,
                           notif_count=notificaciones_no_leidas(slug, 'rector', rector['id']))

# ── RECTOR: CURSOS ─────────────────────────────────────────────────────────────
@app.route('/<slug>/rector/cursos')
def rector_cursos(slug):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    colegio = get_colegio(slug)
    conn = conectar(slug)
    rows = conn.execute(
        '''SELECT curso, jornada, COUNT(*) as total,
                  SUM(CASE WHEN activo=1 THEN 1 ELSE 0 END) as activos
           FROM alumnos GROUP BY curso, jornada ORDER BY curso''').fetchall()
    cursos = [dict(r) for r in rows]
    conn.close()
    return render_template('rector_cursos.html',
                           slug=slug, colegio=colegio, rector=rector,
                           cursos=cursos,
                           notif_count=notificaciones_no_leidas(slug, 'rector', rector['id']))

# ── RECTOR: REPORTES ───────────────────────────────────────────────────────────
@app.route('/<slug>/rector/reportes')
def rector_reportes(slug):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    colegio = get_colegio(slug)
    conn = conectar(slug)
    total_est = conn.execute(
        'SELECT COUNT(*) as c FROM alumnos WHERE activo=1').fetchone()['c']
    total_prof = conn.execute(
        'SELECT COUNT(*) as c FROM profesores WHERE activo=1').fetchone()['c']
    total_cursos = conn.execute(
        'SELECT COUNT(DISTINCT curso) as c FROM alumnos WHERE activo=1').fetchone()['c']
    total_directoras = conn.execute(
        'SELECT COUNT(*) as c FROM directoras WHERE activo=1').fetchone()['c']
    conn.close()
    return render_template('rector_reportes.html',
                           slug=slug, colegio=colegio, rector=rector,
                           total_est=total_est, total_prof=total_prof,
                           total_cursos=total_cursos,
                           total_directoras=total_directoras,
                           notif_count=notificaciones_no_leidas(slug, 'rector', rector['id']))

# ── RECTOR: CONFIGURACIÓN ──────────────────────────────────────────────────────
@app.route('/<slug>/rector/configuracion', methods=['GET', 'POST'])
def rector_configuracion(slug):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    colegio = get_colegio(slug)
    error = exito = None
    conn = conectar(slug)

    accion = request.form.get('accion', '')
    if request.method == 'POST':
        if not validar_csrf():
            return 'Error de seguridad', 400

        if accion == 'perfil':
            nombre = request.form.get('nombre', '').strip()
            email = request.form.get('email', '').strip()
            pw_actual = request.form.get('password_actual', '').strip()
            pw_nueva = request.form.get('password_nueva', '').strip()
            if not nombre:
                error = 'El nombre es obligatorio.'
            elif pw_actual and not verificar_pw(pw_actual, rector['password']):
                error = 'La contraseña actual no es correcta.'
            elif pw_nueva and len(pw_nueva) < 6:
                error = 'Mínimo 6 caracteres para la nueva contraseña.'
            else:
                if pw_nueva:
                    conn.execute('UPDATE rectores SET nombre=?, email=?, password=? WHERE id=?',
                                 (nombre, email, hash_pw(pw_nueva), rector['id']))
                else:
                    conn.execute('UPDATE rectores SET nombre=?, email=? WHERE id=?',
                                 (nombre, email, rector['id']))
                conn.commit()
                exito = 'Perfil actualizado correctamente.'
                rector = conn.execute('SELECT * FROM rectores WHERE id=?', (rector['id'],)).fetchone()

        elif accion == 'institucion':
            tipo_ev = request.form.get('tipo_evaluacion', 'numerica')
            esc_min = request.form.get('escala_min', 1, type=float)
            esc_max = request.form.get('escala_max', 10, type=float)
            nota_min = request.form.get('nota_minima_aprobar', 6, type=float)
            decimales = request.form.get('decimales_notas', 1, type=int)
            num_per = request.form.get('num_periodos', 4, type=int)
            acuse = 1 if request.form.get('acuse_recibo') else 0

            # Nombres personalizados de roles
            roles_json = json.dumps({
                'rector': request.form.get('rol_rector', 'Rector'),
                'authority': request.form.get('rol_authority', 'Coordinador'),
                'teacher': request.form.get('rol_teacher', 'Docente'),
                'student': request.form.get('rol_student', 'Estudiante'),
                'guardian': request.form.get('rol_guardian', 'Acudiente'),
            })

            # Jornadas
            jornadas_raw = request.form.get('jornadas', 'Mañana, Tarde, Nocturna')
            jornadas_list = [j.strip() for j in jornadas_raw.split(',') if j.strip()]
            jornadas_json = json.dumps(jornadas_list)

            conn.execute('''UPDATE config_institucion SET
                tipo_evaluacion=?, escala_min=?, escala_max=?, nota_minima_aprobar=?,
                decimales_notas=?, num_periodos=?, acuse_recibo=?,
                roles_json=?, jornadas_json=?, updated_at=datetime('now','localtime')
                WHERE slug=?''',
                (tipo_ev, esc_min, esc_max, nota_min, decimales, num_per,
                 acuse, roles_json, jornadas_json, slug))
            conn.commit()
            exito = 'Configuración institucional guardada.'

    config = config_get(slug)
    periodos_estado = conn.execute(
        'SELECT * FROM periodos_estado ORDER BY periodo').fetchall()
    conn.close()
    return render_template('rector_configuracion.html',
                           slug=slug, colegio=colegio, rector=rector,
                           config=config, error=error, exito=exito,
                           periodos_estado={r['periodo']: dict(r) for r in periodos_estado},
                           notif_count=notificaciones_no_leidas(slug, 'rector', rector['id']))

@app.route('/<slug>/rector/periodos/<int:periodo>/<accion>', methods=['POST'])
def rector_periodo_accion(slug, periodo, accion):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return ('No autorizado', 403)
    if not validar_csrf(): return ('Error CSRF', 403)
    if accion not in ('abrir', 'cerrar'): return ('Accion invalida', 400)
    conn = conectar(slug)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if accion == 'cerrar':
        conn.execute('''INSERT INTO periodos_estado (periodo, estado, fecha_cierre, cerrado_por)
                        VALUES (?, 'cerrado', ?, ?)
                        ON CONFLICT(periodo) DO UPDATE SET estado='cerrado', fecha_cierre=?, cerrado_por=?''',
                     (periodo, now, rector['id'], now, rector['id']))
        audit_log(slug, rector['id'], 'periodo_cerrado', 'periodos_estado', registro_id=periodo)
    else:
        conn.execute('''INSERT INTO periodos_estado (periodo, estado, fecha_apertura, abierto_por)
                        VALUES (?, 'abierto', ?, ?)
                        ON CONFLICT(periodo) DO UPDATE SET estado='abierto', fecha_apertura=?, abierto_por=?''',
                     (periodo, now, rector['id'], now, rector['id']))
        audit_log(slug, rector['id'], 'periodo_abierto', 'periodos_estado', registro_id=periodo)
    conn.commit()
    conn.close()
    return redirect(url_for('rector_configuracion', slug=slug, _anchor='periodos'))

@app.route('/<slug>/rector/solicitudes')
def rector_solicitudes(slug):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    conn = conectar(slug)
    solicitudes = conn.execute(
        '''SELECT s.*, a.nombre as alumno_nombre, p.nombre as profesor_nombre,
                  COALESCE(ac.nombre, s.campo) as actividad_nombre
           FROM solicitudes_modificacion s
           JOIN alumnos a ON a.id=s.aid
           LEFT JOIN actividades ac ON ac.id=s.actividad_id
           JOIN profesores p ON p.id=s.solicitado_por
           ORDER BY s.creado DESC''').fetchall()
    conn.close()
    return render_template('rector_solicitudes.html',
                           slug=slug, colegio=get_colegio(slug), rector=rector,
                           solicitudes=[dict(s) for s in solicitudes],
                           notif_count=notificaciones_no_leidas(slug, 'rector', rector['id']))

@app.route('/<slug>/rector/solicitudes/<int:sid>/<accion>', methods=['POST'])
def rector_solicitud_accion(slug, sid, accion):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return ('No autorizado', 403)
    if not validar_csrf(): return ('Error CSRF', 403)
    if accion not in ('aprobar', 'rechazar'): return ('Accion invalida', 400)
    conn = conectar(slug)
    sol = conn.execute(
        'SELECT * FROM solicitudes_modificacion WHERE id=?', (sid,)).fetchone()
    if not sol:
        conn.close()
        return ('Solicitud no encontrada', 404)
    respuesta = request.form.get('respuesta', '').strip()
    if accion == 'aprobar':
        conn.execute(
            '''UPDATE solicitudes_modificacion
               SET estado='aprobada', revisado_por=?, respuesta=?, actualizado=datetime('now','localtime')
               WHERE id=?''',
            (rector['id'], respuesta, sid))
        campo = sol['campo'] or 'nota'
        if campo == 'nota' and sol['actividad_id'] is not None:
            conn.execute(
                '''INSERT INTO notas (aid,actividad_id,val) VALUES (?,?,?)
                   ON CONFLICT(aid,actividad_id) DO UPDATE SET val=excluded.val''',
                (sol['aid'], sol['actividad_id'], sol['nota_solicitada']))
        elif campo in ('evaluacion', 'autoevaluacion'):
            profe = conn.execute(
                'SELECT id, jornada FROM asignaciones_materia WHERE profesor_id=? AND materia=? LIMIT 1',
                (sol['solicitado_por'], sol['materia'] or '')).fetchone()
            jornada_eval = profe['jornada'] if profe else ''
            if campo == 'evaluacion':
                conn.execute(
                    '''INSERT INTO evaluaciones (aid,profesor_id,materia,jornada,evaluacion,periodo)
                       VALUES (?,?,?,?,?,?)
                       ON CONFLICT(aid,profesor_id,materia,jornada,periodo)
                       DO UPDATE SET evaluacion=excluded.evaluacion''',
                    (sol['aid'], sol['solicitado_por'], sol['materia'],
                     jornada_eval, sol['nota_solicitada'], sol['periodo']))
            else:
                conn.execute(
                    '''INSERT INTO evaluaciones (aid,profesor_id,materia,jornada,autoevaluacion,periodo)
                       VALUES (?,?,?,?,?,?)
                       ON CONFLICT(aid,profesor_id,materia,jornada,periodo)
                       DO UPDATE SET autoevaluacion=excluded.autoevaluacion''',
                    (sol['aid'], sol['solicitado_por'], sol['materia'],
                     jornada_eval, sol['nota_solicitada'], sol['periodo']))
        audit_log(slug, rector['id'], 'solicitud_aprobada', 'solicitudes_modificacion',
                  registro_id=sid,
                  valor_anterior={'aid': sol['aid'], 'actividad_id': sol['actividad_id'],
                                  'campo': campo, 'val': sol['nota_actual']},
                  valor_nuevo={'aid': sol['aid'], 'actividad_id': sol['actividad_id'],
                               'campo': campo, 'val': sol['nota_solicitada']})
    else:
        conn.execute(
            '''UPDATE solicitudes_modificacion
               SET estado='rechazada', revisado_por=?, respuesta=?, actualizado=datetime('now','localtime')
               WHERE id=?''',
            (rector['id'], respuesta, sid))
        audit_log(slug, rector['id'], 'solicitud_rechazada', 'solicitudes_modificacion',
                  registro_id=sid)
    conn.commit()
    conn.close()
    return redirect(url_for('rector_solicitudes', slug=slug))

@app.route('/<slug>/rector/auditoria')
def rector_auditoria(slug):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    colegio = get_colegio(slug)
    conn = conectar(slug)

    tabla = request.args.get('tabla', '')
    page = max(1, int(request.args.get('page', 1)))
    limit = 50
    offset = (page - 1) * limit

    where = []
    params = []
    if tabla:
        where.append('a.tabla = ?')
        params.append(tabla)

    where_clause = ('WHERE ' + ' AND '.join(where)) if where else ''
    total = conn.execute(f'SELECT COUNT(*) as c FROM audit_log a {where_clause}', params).fetchone()['c']
    registros = conn.execute(f'''
        SELECT a.*, u.nombre as usuario_nombre
        FROM audit_log a
        LEFT JOIN usuarios u ON a.usuario_id = u.id
        {where_clause}
        ORDER BY a.creado DESC LIMIT ? OFFSET ?
    ''', params + [limit, offset]).fetchall()

    tablas = [r['tabla'] for r in conn.execute(
        "SELECT DISTINCT tabla FROM audit_log ORDER BY tabla"
    ).fetchall()]
    conn.close()

    total_pages = max(1, (total + limit - 1) // limit)
    return render_template('rector_auditoria.html',
                         slug=slug, colegio=colegio, rector=rector,
                         registros=[dict(r) for r in registros],
                         tabla=tabla, tablas=tablas,
                         page=page, total_pages=total_pages, total=total,
                         notif_count=notificaciones_no_leidas(slug, 'rector', rector['id']))

# ── NOTIFICATION HELPERS ───────────────────────────────────────────────────────
def crear_notificacion(slug, usuario_tipo, usuario_id, titulo, mensaje='', tipo='info', link=''):
    conn = conectar(slug)
    conn.execute(
        'INSERT INTO notificaciones (usuario_tipo,usuario_id,titulo,mensaje,tipo,link) VALUES (?,?,?,?,?,?)',
        (usuario_tipo, usuario_id, titulo, mensaje, tipo, link))
    conn.commit()
    conn.close()

def notificaciones_no_leidas(slug, usuario_tipo, usuario_id):
    conn = conectar(slug)
    c = conn.execute(
        'SELECT COUNT(*) as c FROM notificaciones WHERE usuario_tipo=? AND usuario_id=? AND leida=0',
        (usuario_tipo, usuario_id)).fetchone()['c']
    conn.close()
    return c

def generar_destinatarios(slug, comunicacion_id):
    try:
        conn = conectar(slug)
    except Exception as e:
        app.logger.error(f'generar_destinatarios: error conectando DB {slug}: {e}')
        return
    try:
        cols_cl = [r[1] for r in conn.execute('PRAGMA table_info(comunicaciones_leidas)').fetchall()]
        if 'leido' not in cols_cl:
            conn.execute('ALTER TABLE comunicaciones_leidas ADD COLUMN leido INTEGER DEFAULT 0')
            conn.commit()
            cols_cl = [r[1] for r in conn.execute('PRAGMA table_info(comunicaciones_leidas)').fetchall()]
    except Exception as e:
        app.logger.error(f'generar_destinatarios: error migrando columna leido: {e}')
    if 'leido' not in cols_cl:
        conn.close()
        app.logger.error('generar_destinatarios: columna leido no disponible en comunicaciones_leidas, abortando')
        return
    com = conn.execute('SELECT * FROM comunicaciones WHERE id=?', (comunicacion_id,)).fetchone()
    if not com:
        conn.close()
        app.logger.warning(f'generar_destinatarios: comunicacion {comunicacion_id} no encontrada')
        return
    if com['estado'] != 'publicado':
        conn.close()
        return
    dest_tipo = com['destinatario_tipo']
    try:
        val_arr = json.loads(com['destinatario_valor']) if com['destinatario_valor'] else []
    except (json.JSONDecodeError, TypeError) as e:
        app.logger.warning(f'generar_destinatarios: error parseando destinatario_valor="{com["destinatario_valor"]}": {e}')
        val_arr = []
    if not isinstance(val_arr, list):
        app.logger.warning(f'generar_destinatarios: destinatario_valor no es un array, ignorando: {type(val_arr).__name__}')
        val_arr = []
    destinatarios = []
    if dest_tipo == 'todo_colegio':
        for r in conn.execute('SELECT id FROM profesores WHERE activo=1').fetchall():
            destinatarios.append(('profesor', r['id']))
        for r in conn.execute('SELECT id FROM directoras WHERE activo=1').fetchall():
            destinatarios.append(('directora', r['id']))
        for r in conn.execute('SELECT id FROM alumnos WHERE activo=1').fetchall():
            destinatarios.append(('estudiante', r['id']))
    elif dest_tipo == 'profesores':
        if val_arr:
            for v in val_arr:
                if isinstance(v, str) and v.startswith('prof_'):
                    try:
                        destinatarios.append(('profesor', int(v.split('_')[1])))
                    except (ValueError, IndexError):
                        app.logger.warning(f'generar_destinatarios: valor prof_ invalido: {v}')
        else:
            for r in conn.execute('SELECT id FROM profesores WHERE activo=1').fetchall():
                destinatarios.append(('profesor', r['id']))
    elif dest_tipo == 'directores':
        if val_arr:
            for v in val_arr:
                if isinstance(v, str) and v.startswith('dir_'):
                    try:
                        destinatarios.append(('directora', int(v.split('_')[1])))
                    except (ValueError, IndexError):
                        app.logger.warning(f'generar_destinatarios: valor dir_ invalido: {v}')
        else:
            for r in conn.execute('SELECT id FROM directoras WHERE activo=1').fetchall():
                destinatarios.append(('directora', r['id']))
    elif dest_tipo == 'estudiantes':
        for r in conn.execute('SELECT id FROM alumnos WHERE activo=1').fetchall():
            destinatarios.append(('estudiante', r['id']))
    elif dest_tipo == 'grado':
        if val_arr:
            cursos_grado = {}
            for row in conn.execute('SELECT DISTINCT curso FROM alumnos WHERE activo=1').fetchall():
                c = row['curso']
                g = ''.join(filter(str.isdigit, c))
                cursos_grado.setdefault(g, []).append(c)
            for grado in val_arr:
                for curso in cursos_grado.get(str(grado), []):
                    for r in conn.execute('SELECT id FROM alumnos WHERE activo=1 AND curso=?', (curso,)).fetchall():
                        destinatarios.append(('estudiante', r['id']))
    elif dest_tipo == 'cursos':
        if val_arr:
            for curso in val_arr:
                for r in conn.execute('SELECT id FROM alumnos WHERE activo=1 AND curso=?', (curso,)).fetchall():
                    destinatarios.append(('estudiante', r['id']))
    for tipo, uid in destinatarios:
        try:
            conn.execute(
                'INSERT OR IGNORE INTO comunicaciones_leidas (comunicacion_id,usuario_tipo,usuario_id,leido) VALUES (?,?,?,0)',
                (comunicacion_id, tipo, uid))
        except Exception as e_insert:
            app.logger.error(f'generar_destinatarios: error insertando destinatario tipo={tipo} uid={uid}: {e_insert}')
    conn.commit()
    conn.close()

def comunicaciones_pendientes(slug, usuario_tipo, usuario_id):
    conn = conectar(slug)
    cols_cl = [r[1] for r in conn.execute('PRAGMA table_info(comunicaciones_leidas)').fetchall()]
    if 'leido' not in cols_cl:
        conn.close()
        return []
    rows = conn.execute(
        '''SELECT c.*, cl.leido, cl.fecha_lectura
           FROM comunicaciones c
           JOIN comunicaciones_leidas cl ON cl.comunicacion_id=c.id
           WHERE cl.usuario_tipo=? AND cl.usuario_id=? AND COALESCE(cl.leido,0)=0
           AND c.estado='publicado' AND c.activo=1
           ORDER BY c.fecha_publicacion DESC''',
        (usuario_tipo, usuario_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── COMUNICACIONES (RECTOR) ────────────────────────────────────────────────────
@app.route('/<slug>/rector/comunicaciones')
def rector_comunicaciones(slug):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    colegio = get_colegio(slug)
    estado_filtro = request.args.get('estado', '')
    conn = conectar(slug)
    if estado_filtro:
        comunicaciones = conn.execute(
            '''SELECT * FROM comunicaciones WHERE rector_id=? AND activo=1 AND estado=?
               ORDER BY fecha_creacion DESC''',
            (rector['id'], estado_filtro)).fetchall()
    else:
        comunicaciones = conn.execute(
            '''SELECT * FROM comunicaciones WHERE rector_id=? AND activo=1
               ORDER BY fecha_creacion DESC''',
            (rector['id'],)).fetchall()
    notif_count = notificaciones_no_leidas(slug, 'rector', rector['id'])
    conn.close()
    return render_template('rector_comunicaciones.html',
                           slug=slug, colegio=colegio, rector=rector,
                           comunicaciones=comunicaciones,
                           estado_filtro=estado_filtro,
                           notif_count=notif_count)

@app.route('/<slug>/rector/comunicaciones/nueva', methods=['GET', 'POST'])
def rector_comunicacion_nueva(slug):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    colegio = get_colegio(slug)
    error = exito = None
    conn = conectar(slug)
    cursos = [r['curso'] for r in conn.execute(
        'SELECT DISTINCT curso FROM alumnos WHERE activo=1 ORDER BY curso').fetchall()]
    profesores = [dict(r) for r in conn.execute(
        'SELECT id, nombre FROM profesores WHERE activo=1 ORDER BY nombre').fetchall()]
    directoras = [dict(r) for r in conn.execute(
        'SELECT id, nombre, curso FROM directoras WHERE activo=1 ORDER BY nombre').fetchall()]
    conn.close()
    if request.method == 'POST':
        if not validar_csrf():
            return 'Error de seguridad', 400
        titulo = request.form.get('titulo', '').strip()
        contenido = request.form.get('contenido', '').strip()
        dest_tipo = request.form.get('destinatario_tipo', '').strip()
        dest_valor = request.form.get('destinatario_valor', '').strip()
        prioridad = request.form.get('prioridad', 'normal').strip()
        programar = request.form.get('fecha_programada', '').strip()
        publicar_ahora = request.form.get('publicar_ahora', '0').strip()
        if not titulo or not contenido or not dest_tipo:
            error = 'Completa todos los campos.'
        else:
            conn = conectar(slug)
            cursor = conn.execute(
                '''INSERT INTO comunicaciones (rector_id,titulo,contenido,destinatario_tipo,destinatario_valor,prioridad,estado,fecha_programada,fecha_publicacion)
                   VALUES (?,?,?,?,?,?,?,?,?)''',
                (rector['id'], titulo, contenido, dest_tipo, dest_valor, prioridad,
                 'publicado' if publicar_ahora == '1' else ('programado' if programar else 'borrador'),
                 programar if programar else None,
                 datetime.today().strftime('%Y-%m-%d %H:%M:%S') if publicar_ahora == '1' else None))
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()
            if publicar_ahora == '1':
                try:
                    generar_destinatarios(slug, new_id)
                except Exception as e:
                    app.logger.error(f'Error en generar_destinatarios (nueva): {e}')
            exito = 'Comunicación creada correctamente.'
    return render_template('rector_comunicacion_form.html',
                           slug=slug, colegio=colegio, rector=rector,
                           error=error, exito=exito, comunicacion=None,
                           cursos=cursos, profesores=profesores,
                           directoras=directoras,
                           notif_count=notificaciones_no_leidas(slug, 'rector', rector['id']))

@app.route('/<slug>/rector/comunicaciones/<int:cid>/editar', methods=['GET', 'POST'])
def rector_comunicacion_editar(slug, cid):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    colegio = get_colegio(slug)
    conn = conectar(slug)
    com = conn.execute(
        'SELECT * FROM comunicaciones WHERE id=? AND rector_id=? AND activo=1',
        (cid, rector['id'])).fetchone()
    if not com: conn.close(); return 'Comunicación no encontrada', 404
    cursos = [r['curso'] for r in conn.execute(
        'SELECT DISTINCT curso FROM alumnos WHERE activo=1 ORDER BY curso').fetchall()]
    profesores = [dict(r) for r in conn.execute(
        'SELECT id, nombre FROM profesores WHERE activo=1 ORDER BY nombre').fetchall()]
    directoras = [dict(r) for r in conn.execute(
        'SELECT id, nombre, curso FROM directoras WHERE activo=1 ORDER BY nombre').fetchall()]
    error = exito = None
    if request.method == 'POST':
        if not validar_csrf():
            return 'Error de seguridad', 400
        titulo = request.form.get('titulo', '').strip()
        contenido = request.form.get('contenido', '').strip()
        dest_tipo = request.form.get('destinatario_tipo', '').strip()
        dest_valor = request.form.get('destinatario_valor', '').strip()
        prioridad = request.form.get('prioridad', 'normal').strip()
        programar = request.form.get('fecha_programada', '').strip()
        publicar_ahora = request.form.get('publicar_ahora', '0').strip()
        if not titulo or not contenido or not dest_tipo:
            error = 'Completa todos los campos.'
        else:
            conn.execute(
                '''UPDATE comunicaciones SET titulo=?,contenido=?,destinatario_tipo=?,destinatario_valor=?,
                   prioridad=?,estado=?,fecha_programada=?,fecha_publicacion=?
                   WHERE id=? AND rector_id=?''',
                (titulo, contenido, dest_tipo, dest_valor, prioridad,
                 'publicado' if publicar_ahora == '1' else ('programado' if programar else com['estado']),
                 programar if programar else None,
                 datetime.today().strftime('%Y-%m-%d %H:%M:%S') if publicar_ahora == '1' else (com['fecha_publicacion'] if com['fecha_publicacion'] else None),
                 cid, rector['id']))
            conn.commit()
            if publicar_ahora == '1':
                conn.close()
                try:
                    generar_destinatarios(slug, cid)
                except Exception as e:
                    app.logger.error(f'Error en generar_destinatarios: {e}')
                conn = conectar(slug)
            exito = 'Comunicación actualizada correctamente.'
            com = conn.execute(
                'SELECT * FROM comunicaciones WHERE id=? AND activo=1', (cid,)).fetchone()
    conn.close()
    return render_template('rector_comunicacion_form.html',
                           slug=slug, colegio=colegio, rector=rector,
                           error=error, exito=exito, comunicacion=com,
                           cursos=cursos, profesores=profesores,
                           directoras=directoras,
                           notif_count=notificaciones_no_leidas(slug, 'rector', rector['id']))

@app.route('/<slug>/rector/comunicaciones/<int:cid>')
def rector_comunicacion_detalle(slug, cid):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    colegio = get_colegio(slug)
    conn = conectar(slug)
    com = conn.execute(
        'SELECT * FROM comunicaciones WHERE id=? AND rector_id=? AND activo=1',
        (cid, rector['id'])).fetchone()
    if not com: conn.close(); return 'Comunicación no encontrada', 404
    total_dest = conn.execute(
        'SELECT COUNT(*) as c FROM comunicaciones_leidas WHERE comunicacion_id=?', (cid,)).fetchone()['c']
    leidas_count = conn.execute(
        'SELECT COUNT(*) as c FROM comunicaciones_leidas WHERE comunicacion_id=? AND leido=1', (cid,)).fetchone()['c']
    no_leidas = total_dest - leidas_count
    conn.close()
    return render_template('rector_comunicacion_detail.html',
                           slug=slug, colegio=colegio, rector=rector,
                           com=com, total_dest=total_dest, leidas=leidas_count, no_leidas=no_leidas,
                           notif_count=notificaciones_no_leidas(slug, 'rector', rector['id']))

@app.route('/<slug>/rector/comunicaciones/<int:cid>/publicar', methods=['POST'])
def rector_comunicacion_publicar(slug, cid):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    if not validar_csrf(): return 'Error de seguridad', 400
    conn = conectar(slug)
    conn.execute(
        '''UPDATE comunicaciones SET estado='publicado',fecha_publicacion=datetime('now','localtime')
           WHERE id=? AND rector_id=? AND activo=1''',
        (cid, rector['id']))
    conn.commit()
    conn.close()
    try:
        generar_destinatarios(slug, cid)
    except Exception as e:
        app.logger.error(f'Error en generar_destinatarios (publicar): {e}')
    return redirect(url_for('rector_comunicaciones', slug=slug))

@app.route('/<slug>/rector/comunicaciones/<int:cid>/archivar', methods=['POST'])
def rector_comunicacion_archivar(slug, cid):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    if not validar_csrf(): return 'Error de seguridad', 400
    conn = conectar(slug)
    conn.execute(
        "UPDATE comunicaciones SET estado='archivado' WHERE id=? AND rector_id=? AND activo=1",
        (cid, rector['id']))
    conn.commit()
    conn.close()
    return redirect(url_for('rector_comunicaciones', slug=slug))

@app.route('/<slug>/rector/comunicaciones/<int:cid>/eliminar', methods=['POST'])
def rector_comunicacion_eliminar(slug, cid):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('login', slug=slug))
    if not validar_csrf(): return 'Error de seguridad', 400
    conn = conectar(slug)
    conn.execute(
        'DELETE FROM comunicaciones WHERE id=? AND rector_id=?',
        (cid, rector['id']))
    conn.execute('DELETE FROM comunicaciones_leidas WHERE comunicacion_id=?', (cid,))
    conn.commit()
    conn.close()
    return redirect(url_for('rector_comunicaciones', slug=slug))

# ── NOTIFICACIONES (TODOS LOS ROLES) ───────────────────────────────────────────
@app.route('/<slug>/notificaciones')
def notificaciones(slug):
    require_colegio(slug)
    colegio = get_colegio(slug)
    usuario_tipo = None
    usuario_id = None
    rector = get_rector(slug)
    if rector: usuario_tipo, usuario_id = 'rector', rector['id']
    if not usuario_id:
        prof = get_profesor(slug)
        if prof: usuario_tipo, usuario_id = 'profesor', prof['id']
    if not usuario_id:
        directora = get_directora(slug)
        if directora: usuario_tipo, usuario_id = 'directora', directora['id']
    if not usuario_id:
        aid = session.get(f'alumno_id_{slug}')
        if aid: usuario_tipo, usuario_id = 'estudiante', aid
    if not usuario_id:
        return redirect(url_for('login', slug=slug))
    conn = conectar(slug)
    notifs = conn.execute(
        'SELECT * FROM notificaciones WHERE usuario_tipo=? AND usuario_id=? ORDER BY fecha_creacion DESC LIMIT 100',
        (usuario_tipo, usuario_id)).fetchall()
    conn.close()
    return render_template('notificaciones.html',
                           slug=slug, colegio=colegio,
                           notificaciones=notifs,
                           usuario_tipo=usuario_tipo)

@app.route('/<slug>/notificaciones/<int:nid>/leer', methods=['POST'])
def notificacion_leer(slug, nid):
    require_colegio(slug)
    if not validar_csrf(): return 'Error de seguridad', 400
    usuario_tipo = None; usuario_id = None
    rector = get_rector(slug)
    if rector: usuario_tipo, usuario_id = 'rector', rector['id']
    if not usuario_id:
        prof = get_profesor(slug)
        if prof: usuario_tipo, usuario_id = 'profesor', prof['id']
    if not usuario_id:
        directora = get_directora(slug)
        if directora: usuario_tipo, usuario_id = 'directora', directora['id']
    if not usuario_id:
        aid = session.get(f'alumno_id_{slug}')
        if aid: usuario_tipo, usuario_id = 'estudiante', aid
    if not usuario_id:
        return jsonify({'ok': False, 'mensaje': 'No autorizado'}), 403
    conn = conectar(slug)
    conn.execute('UPDATE notificaciones SET leida=1 WHERE id=? AND usuario_tipo=? AND usuario_id=?',
                 (nid, usuario_tipo, usuario_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/<slug>/notificaciones/contar')
def notificaciones_contar(slug):
    require_colegio(slug)
    usuario_tipo = None
    usuario_id = None
    rector = get_rector(slug)
    if rector: usuario_tipo, usuario_id = 'rector', rector['id']
    if not usuario_id:
        prof = get_profesor(slug)
        if prof: usuario_tipo, usuario_id = 'profesor', prof['id']
    if not usuario_id:
        directora = get_directora(slug)
        if directora: usuario_tipo, usuario_id = 'directora', directora['id']
    if not usuario_id:
        aid = session.get(f'alumno_id_{slug}')
        if aid: usuario_tipo, usuario_id = 'estudiante', aid
    if not usuario_id:
        return jsonify({'count': 0})
    c = notificaciones_no_leidas(slug, usuario_tipo, usuario_id)
    return jsonify({'count': c})

@app.route('/<slug>/comunicaciones/<int:cid>/leer', methods=['POST'])
def comunicacion_leer(slug, cid):
    if not validar_csrf(): return jsonify({'error': 'Error CSRF'}), 403
    require_colegio(slug)
    usuario_tipo = None
    usuario_id = None
    rector = get_rector(slug)
    if rector: usuario_tipo, usuario_id = 'rector', rector['id']
    if not usuario_id:
        prof = get_profesor(slug)
        if prof: usuario_tipo, usuario_id = 'profesor', prof['id']
    if not usuario_id:
        directora = get_directora(slug)
        if directora: usuario_tipo, usuario_id = 'directora', directora['id']
    if not usuario_id:
        aid = session.get(f'alumno_id_{slug}')
        if aid: usuario_tipo, usuario_id = 'estudiante', aid
    if not usuario_id:
        return jsonify({'error': 'No autorizado'}), 403
    conn = conectar(slug)
    try:
        cols_cl = [r[1] for r in conn.execute('PRAGMA table_info(comunicaciones_leidas)').fetchall()]
        if 'leido' not in cols_cl:
            conn.execute('ALTER TABLE comunicaciones_leidas ADD COLUMN leido INTEGER DEFAULT 0')
            conn.commit()
            cols_cl = [r[1] for r in conn.execute('PRAGMA table_info(comunicaciones_leidas)').fetchall()]
        if 'leido' not in cols_cl:
            conn.close()
            return jsonify({'error': 'Error de migración'}), 500
    except Exception as e:
        app.logger.error(f'comunicacion_leer: error migrando columna leido: {e}')
    existing = conn.execute(
        'SELECT 1 FROM comunicaciones_leidas WHERE comunicacion_id=? AND usuario_tipo=? AND usuario_id=?',
        (cid, usuario_tipo, usuario_id)).fetchone()
    if existing:
        conn.execute(
            'UPDATE comunicaciones_leidas SET leido=1, fecha_lectura=datetime(\'now\',\'localtime\') WHERE comunicacion_id=? AND usuario_tipo=? AND usuario_id=?',
            (cid, usuario_tipo, usuario_id))
    else:
        conn.execute(
            'INSERT INTO comunicaciones_leidas (comunicacion_id,usuario_tipo,usuario_id,leido,fecha_lectura) VALUES (?,?,?,1,datetime(\'now\',\'localtime\'))',
            (cid, usuario_tipo, usuario_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ── CANALES CRUD (Rector) ──────────────────────────────────────────────────────
@app.route('/<slug>/rector/canales')
def rector_canales(slug):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return redirect(url_for('rector_login', slug=slug))
    conn = conectar(slug)
    canales = conn.execute('SELECT * FROM canales WHERE slug=? ORDER BY fecha_creacion DESC', (slug,)).fetchall()
    cursos = conn.execute('SELECT DISTINCT curso FROM alumnos WHERE activo=1 ORDER BY curso').fetchall()
    materias_rows = conn.execute('SELECT DISTINCT materia FROM actividades').fetchall()
    if not materias_rows:
        materias_rows = conn.execute('SELECT DISTINCT materia FROM asignaciones_materia').fetchall()
    materias = list(set(r['materia'] for r in materias_rows))
    conn.close()
    colegio = get_colegio(slug)
    return render_template('rector_canales.html', slug=slug, rector=rector, canales=canales, colegio=colegio,
                          cursos=[r['curso'] for r in cursos],
                          materias=materias)

@app.route('/<slug>/rector/canales/crear', methods=['POST'])
def rector_canales_crear(slug):
    if not validar_csrf(): return jsonify({'ok': False, 'error': 'Error CSRF'}), 403
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return jsonify({'ok':False,'error':'No autorizado'})
    tipo = request.form.get('tipo')
    nombre = request.form.get('nombre','').strip()
    curso = request.form.get('curso','')
    materia = request.form.get('materia','')
    descripcion = request.form.get('descripcion','')
    if not nombre:
        nombres = {'institucional':'Institucional','rectoria':'Rectoría','profesores':'Profesores',
                   'director_curso':f'Directores {curso}','curso':f'Curso {curso}','materia':f'Materia {materia}'}
        nombre = nombres.get(tipo, tipo)
    conn = conectar(slug)
    cid = conn.execute('INSERT INTO canales (slug,rector_id,tipo,nombre,descripcion,curso,materia) VALUES (?,?,?,?,?,?,?)',
                       (slug,rector['id'],tipo,nombre,descripcion,curso,materia)).lastrowid
    asignar_miembros_auto(conn, slug, cid, tipo, curso, materia)
    conn.commit()
    conn.close()
    return jsonify({'ok':True, 'canal_id':cid})

@app.route('/<slug>/rector/canales/<int:cid>/eliminar', methods=['POST'])
def rector_canales_eliminar(slug, cid):
    if not validar_csrf(): return jsonify({'ok': False, 'error': 'Error CSRF'}), 403
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return jsonify({'ok':False,'error':'No autorizado'})
    conn = conectar(slug)
    conn.execute('UPDATE canales SET activo=0 WHERE id=? AND slug=?', (cid, slug))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/<slug>/rector/canales/<int:cid>/miembros')
def rector_canales_miembros(slug, cid):
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return jsonify({'ok':False,'error':'No autorizado'})
    conn = conectar(slug)
    miembros = conn.execute('SELECT * FROM canal_miembros WHERE canal_id=?', (cid,)).fetchall()
    canal = conn.execute('SELECT * FROM canales WHERE id=?', (cid,)).fetchone()
    conn.close()
    data = [dict(m) for m in miembros]
    for m in data:
        conn2 = conectar(slug)
        m['nombre_usuario'] = nombre_usuario_canal(conn2, m['usuario_tipo'], m['usuario_id'])
        conn2.close()
    return jsonify({'ok':True, 'miembros':data, 'canal':dict(canal) if canal else None})

# ── CANALES API (usuarios) ─────────────────────────────────────────────────────
@app.route('/<slug>/api/canales')
def api_canales(slug):
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify({'ok':False,'error':'No autenticado'}), 401
    if tipo == 'rector':
        rector = get_rector(slug)
        conn = conectar(slug)
        rows = conn.execute('''
            SELECT c.*,
                (SELECT mensaje FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_mensaje,
                (SELECT usuario_tipo FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_autor_tipo,
                (SELECT usuario_id FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_autor_id,
                (SELECT fecha FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultima_fecha,
                (SELECT COUNT(*) FROM mensajes_canal mc
                 LEFT JOIN mensajes_leidos ml ON ml.mensaje_id=mc.id AND ml.usuario_tipo='rector' AND ml.usuario_id=?
                 WHERE mc.canal_id=c.id AND ml.id IS NULL) as no_leidos
            FROM canales c WHERE c.activo=1 ORDER BY ultima_fecha DESC''', (rector['id'],)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    return jsonify(canales_usuario(slug, tipo, uid))

def _enriquecer_mensaje(conn, d):
    d['archivos'] = archivos_por_mensaje(conn, d['id'])
    d['reacciones'] = reacciones_por_mensaje(conn, d['id'])
    if d.get('responde_a'):
        padre = conn.execute('SELECT id, mensaje, usuario_tipo, usuario_id FROM mensajes_canal WHERE id=?', (d['responde_a'],)).fetchone()
        if padre:
            d['responde_a_info'] = {
                'id': padre['id'],
                'mensaje': padre['mensaje'][:120],
                'autor_nombre': nombre_usuario_canal(conn, padre['usuario_tipo'], padre['usuario_id'])
            }
    return d

@app.route('/<slug>/api/canales/<int:cid>/mensajes')
def api_canales_mensajes(slug, cid):
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify([])
    conn = conectar(slug)
    canal = conn.execute('SELECT * FROM canales WHERE id=? AND activo=1', (cid,)).fetchone()
    if not canal: conn.close(); return jsonify([])
    if tipo != 'rector':
        miembro = conn.execute('SELECT 1 FROM canal_miembros WHERE canal_id=? AND usuario_tipo=? AND usuario_id=?',
                              (cid, tipo, uid)).fetchone()
        if not miembro: conn.close(); return jsonify([])
    mensajes = conn.execute('''
        SELECT m.*, COALESCE(ml.id,0) as leido
        FROM mensajes_canal m
        LEFT JOIN mensajes_leidos ml ON ml.mensaje_id=m.id AND ml.usuario_tipo=? AND ml.usuario_id=?
        WHERE m.canal_id=? AND m.eliminado=0 ORDER BY m.id ASC''', (tipo, uid, cid)).fetchall()
    result = []
    for r in mensajes:
        d = dict(r)
        d['autor_nombre'] = nombre_usuario_canal(conn, r['usuario_tipo'], r['usuario_id'])
        _enriquecer_mensaje(conn, d)
        result.append(d)
    conn.close()
    return jsonify(result)

@app.route('/<slug>/api/canales/<int:cid>/mensajes/nuevos')
def api_canales_mensajes_nuevos(slug, cid):
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify({'ok':False,'error':'No autenticado'}), 401
    ultimo_id = request.args.get('ultimo_id', 0, type=int)
    conn = conectar(slug)
    canal = conn.execute('SELECT * FROM canales WHERE id=? AND activo=1', (cid,)).fetchone()
    if not canal: conn.close(); return jsonify({'ok':False,'error':'Canal no encontrado'})
    if tipo != 'rector':
        miembro = conn.execute('SELECT 1 FROM canal_miembros WHERE canal_id=? AND usuario_tipo=? AND usuario_id=?',
                              (cid, tipo, uid)).fetchone()
        if not miembro: conn.close(); return jsonify({'ok':False,'error':'No eres miembro'})
    mensajes = conn.execute('''
        SELECT m.*, COALESCE(ml.id,0) as leido
        FROM mensajes_canal m
        LEFT JOIN mensajes_leidos ml ON ml.mensaje_id=m.id AND ml.usuario_tipo=? AND ml.usuario_id=?
        WHERE m.canal_id=? AND m.id > ? AND m.eliminado=0 ORDER BY m.id ASC''',
        (tipo, uid, cid, ultimo_id)).fetchall()
    result = []
    for r in mensajes:
        d = dict(r)
        d['autor_nombre'] = nombre_usuario_canal(conn, r['usuario_tipo'], r['usuario_id'])
        _enriquecer_mensaje(conn, d)
        result.append(d)
    conn.close()
    return jsonify({'ok':True, 'mensajes':result})

@app.route('/<slug>/api/canales/<int:cid>/enviar', methods=['POST'])
def api_canales_enviar(slug, cid):
    if not validar_csrf(): return jsonify({'ok': False, 'error': 'Error CSRF'}), 403
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify({'ok':False,'error':'No autorizado'})
    mensaje = request.form.get('mensaje','').strip()
    responde_a = request.form.get('responde_a', type=int)
    tiene_archivos = 0
    conn = conectar(slug)
    canal = conn.execute('SELECT * FROM canales WHERE id=? AND activo=1', (cid,)).fetchone()
    if not canal: conn.close(); return jsonify({'ok':False,'error':'Canal no encontrado'})
    if tipo != 'rector':
        miembro = conn.execute('SELECT 1 FROM canal_miembros WHERE canal_id=? AND usuario_tipo=? AND usuario_id=?',
                              (cid, tipo, uid)).fetchone()
        if not miembro: conn.close(); return jsonify({'ok':False,'error':'No eres miembro'})
    mid = conn.execute(
        'INSERT INTO mensajes_canal (canal_id,usuario_tipo,usuario_id,mensaje,responde_a,tiene_archivos) VALUES (?,?,?,?,?,?)',
        (cid, tipo, uid, mensaje, responde_a, tiene_archivos)).lastrowid
    archivos_subidos = []
    if request.files:
        for key in request.files:
            f = request.files[key]
            if f and f.filename:
                fid, err = guardar_archivo_mensaje(slug, cid, f, tipo, uid)
                if fid:
                    conn.execute('UPDATE mensajes_archivos SET mensaje_id=? WHERE id=?', (mid, fid))
                    archivos_subidos.append(fid)
                    tiene_archivos = 1
    if tiene_archivos:
        conn.execute('UPDATE mensajes_canal SET tiene_archivos=1 WHERE id=?', (mid,))
    # Actualizar canal_actividad
    conn.execute('INSERT OR REPLACE INTO canal_actividad (canal_id, usuario_tipo, usuario_id, estado, ultima_vista) VALUES (?,?,?,?,?)',
                (cid, tipo, uid, 'online', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    return jsonify({'ok':True, 'mensaje_id':mid, 'archivos': archivos_subidos})

@app.route('/<slug>/api/canales/<int:cid>/leer', methods=['POST'])
def api_canales_leer(slug, cid):
    if not validar_csrf(): return jsonify({'ok': False, 'error': 'Error CSRF'}), 403
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify({'ok':False})
    conn = conectar(slug)
    msgs = conn.execute('SELECT id FROM mensajes_canal WHERE canal_id=?', (cid,)).fetchall()
    for m in msgs:
        conn.execute('INSERT OR IGNORE INTO mensajes_leidos (mensaje_id,usuario_tipo,usuario_id) VALUES (?,?,?)',
                    (m['id'], tipo, uid))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

# ── FASE 5 – ARCHIVOS ─────────────────────────────────────────────────────────
@app.route('/<slug>/api/canales/<int:cid>/archivos/subir', methods=['POST'])
def api_canales_subir_archivos(slug, cid):
    if not validar_csrf(): return jsonify({'ok':False,'error':'CSRF'}), 403
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify({'ok':False,'error':'No autorizado'}), 401
    if 'archivo' not in request.files: return jsonify({'ok':False,'error':'No hay archivo'}), 400
    f = request.files['archivo']
    if not f.filename: return jsonify({'ok':False,'error':'Archivo vacío'}), 400
    fid, err = guardar_archivo_mensaje(slug, cid, f, tipo, uid)
    if err: return jsonify({'ok':False,'error':err}), 400
    return jsonify({'ok':True, 'archivo_id': fid})

@app.route('/<slug>/api/archivos/<int:fid>/descargar')
def api_archivo_descargar(slug, fid):
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return 'No autorizado', 401
    conn = conectar(slug)
    arch = conn.execute('SELECT * FROM mensajes_archivos WHERE id=?', (fid,)).fetchone()
    conn.close()
    if not arch: return 'No encontrado', 404
    ruta = os.path.join(app.root_path, 'static', 'uploads', slug, arch['nombre_archivo'])
    if not os.path.exists(ruta): return 'No encontrado', 404
    return send_file(ruta, mimetype=arch['tipo_mime'], as_attachment=True,
                     download_name=arch['nombre_original'])

@app.route('/<slug>/api/archivos/<int:fid>/previsualizar')
def api_archivo_previsualizar(slug, fid):
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return 'No autorizado', 401
    conn = conectar(slug)
    arch = conn.execute('SELECT * FROM mensajes_archivos WHERE id=?', (fid,)).fetchone()
    conn.close()
    if not arch: return 'No encontrado', 404
    ruta = os.path.join(app.root_path, 'static', 'uploads', slug, arch['nombre_archivo'])
    if not os.path.exists(ruta): return 'No encontrado', 404
    if arch['es_imagen']:
        return send_file(ruta, mimetype=arch['tipo_mime'])
    if arch['tipo_mime'] == 'application/pdf':
        return send_file(ruta, mimetype='application/pdf')
    return jsonify({'ok':False,'error':'Vista previa no disponible'})

@app.route('/<slug>/api/archivos/<int:fid>/eliminar', methods=['DELETE','POST'])
def api_archivo_eliminar(slug, fid):
    if not validar_csrf(): return jsonify({'ok':False,'error':'CSRF'}), 403
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify({'ok':False,'error':'No autorizado'}), 401
    conn = conectar(slug)
    arch = conn.execute('SELECT * FROM mensajes_archivos WHERE id=?', (fid,)).fetchone()
    if not arch: conn.close(); return jsonify({'ok':False,'error':'No encontrado'}), 404
    if arch['usuario_tipo'] != tipo or arch['usuario_id'] != uid:
        if tipo != 'rector':
            conn.close(); return jsonify({'ok':False,'error':'No puedes eliminar este archivo'}), 403
    conn.execute('DELETE FROM mensajes_archivos WHERE id=?', (fid,))
    conn.commit()
    audit_log(slug, uid, 'delete', 'mensajes_archivos', fid,
              valor_anterior={'nombre_original': arch['nombre_original']})
    conn.close()
    ruta = os.path.join(app.root_path, 'static', 'uploads', slug, arch['nombre_archivo'])
    try: os.remove(ruta)
    except Exception: pass
    return jsonify({'ok':True})

# ── FASE 5 – REACCIONES ───────────────────────────────────────────────────────
@app.route('/<slug>/api/canales/<int:cid>/reaccionar', methods=['POST'])
def api_canales_reaccionar(slug, cid):
    if not validar_csrf(): return jsonify({'ok':False,'error':'CSRF'}), 403
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify({'ok':False,'error':'No autorizado'}), 401
    mensaje_id = request.form.get('mensaje_id', type=int)
    reaccion = request.form.get('reaccion','').strip()
    if not mensaje_id or reaccion not in ('👍','✅','❓','📌','❤'):
        return jsonify({'ok':False,'error':'Reacción inválida'}), 400
    conn = conectar(slug)
    existing = conn.execute(
        'SELECT id FROM mensajes_reacciones WHERE mensaje_id=? AND usuario_tipo=? AND usuario_id=? AND reaccion=?',
        (mensaje_id, tipo, uid, reaccion)).fetchone()
    if existing:
        conn.execute('DELETE FROM mensajes_reacciones WHERE id=?', (existing['id'],))
        conn.commit(); conn.close()
        return jsonify({'ok':True, 'activo':False})
    conn.execute('INSERT OR IGNORE INTO mensajes_reacciones (mensaje_id,usuario_tipo,usuario_id,reaccion) VALUES (?,?,?,?)',
                (mensaje_id, tipo, uid, reaccion))
    conn.commit(); conn.close()
    return jsonify({'ok':True, 'activo':True})

# ── FASE 5 – MENSAJES FIJADOS ─────────────────────────────────────────────────
@app.route('/<slug>/api/canales/<int:cid>/fijar', methods=['POST'])
def api_canales_fijar(slug, cid):
    if not validar_csrf(): return jsonify({'ok':False,'error':'CSRF'}), 403
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify({'ok':False,'error':'No autorizado'}), 401
    mensaje_id = request.form.get('mensaje_id', type=int)
    if not mensaje_id: return jsonify({'ok':False,'error':'mensaje_id requerido'}), 400
    conn = conectar(slug)
    existing = conn.execute('SELECT id FROM mensajes_fijados WHERE canal_id=? AND mensaje_id=?',
                           (cid, mensaje_id)).fetchone()
    if existing:
        conn.execute('DELETE FROM mensajes_fijados WHERE id=?', (existing['id'],))
        conn.commit(); conn.close()
        return jsonify({'ok':True, 'fijado':False})
    conn.execute('INSERT INTO mensajes_fijados (canal_id,mensaje_id,fijado_por_tipo,fijado_por_id) VALUES (?,?,?,?)',
                (cid, mensaje_id, tipo, uid))
    conn.commit(); conn.close()
    return jsonify({'ok':True, 'fijado':True})

@app.route('/<slug>/api/canales/<int:cid>/fijados')
def api_canales_fijados(slug, cid):
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify([])
    conn = conectar(slug)
    rows = conn.execute(
        '''SELECT m.id, m.mensaje, m.usuario_tipo, m.usuario_id, m.fecha, m.editado,
                  f.fecha as fijado_en, f.fijado_por_tipo, f.fijado_por_id
           FROM mensajes_fijados f
           JOIN mensajes_canal m ON m.id=f.mensaje_id
           WHERE f.canal_id=? AND m.eliminado=0
           ORDER BY f.id DESC''', (cid,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['autor_nombre'] = nombre_usuario_canal(conn, r['usuario_tipo'], r['usuario_id'])
        result.append(d)
    conn.close()
    return jsonify(result)

# ── FASE 5 – BIBLIOTECA DEL CANAL ─────────────────────────────────────────────
@app.route('/<slug>/api/canales/<int:cid>/biblioteca')
def api_canales_biblioteca(slug, cid):
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify({})
    conn = conectar(slug)
    archivos = [dict(r) for r in conn.execute(
        'SELECT * FROM mensajes_archivos WHERE canal_id=? ORDER BY fecha DESC LIMIT 50', (cid,)).fetchall()]
    enlaces = [dict(r) for r in conn.execute(
        'SELECT * FROM canal_enlaces WHERE canal_id=? ORDER BY fecha DESC LIMIT 50', (cid,)).fetchall()]
    conn.close()
    return jsonify({'archivos': archivos, 'enlaces': enlaces})

# ── FASE 5 – BUSCAR EN EL CANAL ───────────────────────────────────────────────
@app.route('/<slug>/api/canales/<int:cid>/buscar')
def api_canales_buscar(slug, cid):
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify([])
    q = request.args.get('q','').strip()
    autor = request.args.get('autor','').strip()
    desde = request.args.get('desde','').strip()
    hasta = request.args.get('hasta','').strip()
    conn = conectar(slug)
    sql = 'SELECT m.* FROM mensajes_canal m WHERE m.canal_id=? AND m.eliminado=0'
    params = [cid]
    if q:
        sql += ' AND m.mensaje LIKE ?'
        params.append(f'%{q}%')
    if autor:
        sql += ' AND (SELECT nombre FROM profesores WHERE id=m.usuario_id AND m.usuario_tipo=\'profesor\') LIKE ?'
        params.append(f'%{autor}%')
    if desde:
        sql += ' AND m.fecha >= ?'
        params.append(desde)
    if hasta:
        sql += ' AND m.fecha <= ?'
        params.append(hasta + ' 23:59:59')
    sql += ' ORDER BY m.id DESC LIMIT 100'
    rows = conn.execute(sql, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['autor_nombre'] = nombre_usuario_canal(conn, r['usuario_tipo'], r['usuario_id'])
        _enriquecer_mensaje(conn, d)
        result.append(d)
    conn.close()
    return jsonify(result)

# ── FASE 5 – EDITAR / ELIMINAR MENSAJES ────────────────────────────────────────
TIEMPO_EDICION_SEGUNDOS = 300  # 5 minutos, configurable

@app.route('/<slug>/api/canales/<int:cid>/editar/<int:mid>', methods=['POST'])
def api_canales_editar(slug, cid, mid):
    if not validar_csrf(): return jsonify({'ok':False,'error':'CSRF'}), 403
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify({'ok':False,'error':'No autorizado'}), 401
    conn = conectar(slug)
    msg = conn.execute('SELECT * FROM mensajes_canal WHERE id=? AND canal_id=?', (mid, cid)).fetchone()
    if not msg: conn.close(); return jsonify({'ok':False,'error':'No encontrado'}), 404
    if msg['usuario_tipo'] != tipo or msg['usuario_id'] != uid:
        conn.close(); return jsonify({'ok':False,'error':'No puedes editar este mensaje'}), 403
    if msg['eliminado']:
        conn.close(); return jsonify({'ok':False,'error':'Mensaje eliminado'}), 400
    try:
        creado = datetime.strptime(msg['fecha'], '%Y-%m-%d %H:%M:%S') if msg['fecha'] else datetime.min
    except (ValueError, TypeError):
        creado = datetime.min
    if (datetime.now() - creado).total_seconds() > TIEMPO_EDICION_SEGUNDOS:
        conn.close(); return jsonify({'ok':False,'error':'Tiempo de edición expirado'}), 400
    nuevo_texto = request.form.get('mensaje','').strip()
    if not nuevo_texto: conn.close(); return jsonify({'ok':False,'error':'Mensaje vacío'}), 400
    viejo_texto = msg['mensaje']
    conn.execute('UPDATE mensajes_canal SET mensaje=?, editado=editado+1, editado_en=? WHERE id=?',
                (nuevo_texto, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), mid))
    conn.commit()
    audit_log(slug, uid, 'update', 'mensajes_canal', mid,
              valor_anterior={'mensaje': viejo_texto},
              valor_nuevo={'mensaje': nuevo_texto})
    conn.close()
    return jsonify({'ok':True})

@app.route('/<slug>/api/canales/<int:cid>/eliminar/<int:mid>', methods=['DELETE','POST'])
def api_canales_eliminar(slug, cid, mid):
    if not validar_csrf(): return jsonify({'ok':False,'error':'CSRF'}), 403
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify({'ok':False,'error':'No autorizado'}), 401
    conn = conectar(slug)
    msg = conn.execute('SELECT * FROM mensajes_canal WHERE id=? AND canal_id=?', (mid, cid)).fetchone()
    if not msg: conn.close(); return jsonify({'ok':False,'error':'No encontrado'}), 404
    if msg['usuario_tipo'] != tipo or msg['usuario_id'] != uid:
        conn.close(); return jsonify({'ok':False,'error':'No puedes eliminar este mensaje'}), 403
    conn.execute('UPDATE mensajes_canal SET eliminado=1 WHERE id=?', (mid,))
    conn.commit()
    audit_log(slug, uid, 'delete', 'mensajes_canal', mid,
              valor_anterior={'mensaje': msg['mensaje'][:200]})
    conn.close()
    return jsonify({'ok':True})

# ── FASE 5 – LECTURAS ──────────────────────────────────────────────────────────
@app.route('/<slug>/api/canales/<int:cid>/lecturas')
def api_canales_lecturas(slug, cid):
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify([])
    conn = conectar(slug)
    miembros = conn.execute(
        'SELECT usuario_tipo, usuario_id FROM canal_miembros WHERE canal_id=?', (cid,)).fetchall()
    total_msg = conn.execute(
        'SELECT COUNT(*) as c FROM mensajes_canal WHERE canal_id=? AND eliminado=0', (cid,)).fetchone()['c']
    ult_vistas = {}
    for row in conn.execute(
        'SELECT usuario_tipo, usuario_id, ultima_vista FROM canal_actividad WHERE canal_id=?',
        (cid,)).fetchall():
        ult_vistas[f"{row['usuario_tipo']}_{row['usuario_id']}"] = row['ultima_vista']
    leidos_por_miembro = {}
    for row in conn.execute(
        '''SELECT ml.usuario_tipo, ml.usuario_id, COUNT(DISTINCT mc.id) as c
           FROM mensajes_leidos ml
           JOIN mensajes_canal mc ON ml.mensaje_id=mc.id
           WHERE mc.canal_id=? AND mc.eliminado=0
           GROUP BY ml.usuario_tipo, ml.usuario_id''',
        (cid,)).fetchall():
        leidos_por_miembro[f"{row['usuario_tipo']}_{row['usuario_id']}"] = row['c']
    result = {}
    for m in miembros:
        nombre = nombre_usuario_canal(conn, m['usuario_tipo'], m['usuario_id'])
        key = f"{m['usuario_tipo']}_{m['usuario_id']}"
        result[key] = {
            'nombre': nombre,
            'tipo': m['usuario_tipo'],
            'total': total_msg,
            'leidos': leidos_por_miembro.get(key, 0),
            'ultima_vista': ult_vistas.get(key),
        }
    conn.close()
    return jsonify(result)

# ── FASE 5 – ESCRIBIENDO / ACTIVIDAD ──────────────────────────────────────────
@app.route('/<slug>/api/canales/<int:cid>/escribiendo', methods=['POST'])
def api_canales_escribiendo(slug, cid):
    if not validar_csrf(): return jsonify({'ok':False,'error':'CSRF'}), 403
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify({'ok':False})
    conn = conectar(slug)
    conn.execute('INSERT OR REPLACE INTO canal_actividad (canal_id,usuario_tipo,usuario_id,estado,ultima_vista) VALUES (?,?,?,?,?)',
                (cid, tipo, uid, 'typing', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/<slug>/api/canales/<int:cid>/actividad')
def api_canales_actividad(slug, cid):
    require_colegio(slug)
    conn = conectar(slug)
    rows = conn.execute(
        '''SELECT ca.*
           FROM canal_actividad ca
           WHERE ca.canal_id=?''', (cid,)).fetchall()
    result = {}
    now = datetime.now()
    for r in rows:
        estado = r['estado']
        ult_vista = datetime.strptime(r['ultima_vista'], '%Y-%m-%d %H:%M:%S') if r['ultima_vista'] else None
        if estado == 'typing' and ult_vista and (now - ult_vista).total_seconds() > 8:
            estado = 'online'
        if ult_vista and (now - ult_vista).total_seconds() > 120:
            estado = 'offline'
        nombre = nombre_usuario_canal(conn, r['usuario_tipo'], r['usuario_id'])
        key = f"{r['usuario_tipo']}_{r['usuario_id']}"
        result[key] = {'estado': estado, 'nombre': nombre, 'ultima_vista': r['ultima_vista']}
    conn.close()
    return jsonify(result)

# ── FASE 5 – GUARDAR ENLACE ───────────────────────────────────────────────────
@app.route('/<slug>/api/canales/<int:cid>/enlaces', methods=['POST'])
def api_canales_guardar_enlace(slug, cid):
    if not validar_csrf(): return jsonify({'ok':False,'error':'CSRF'}), 403
    require_colegio(slug)
    tipo, uid = get_usuario_actual(slug)
    if not tipo: return jsonify({'ok':False,'error':'No autorizado'}), 401
    url = request.form.get('url','').strip()
    titulo = request.form.get('titulo','').strip()
    if not url: return jsonify({'ok':False,'error':'URL requerida'}), 400
    conn = conectar(slug)
    conn.execute('INSERT INTO canal_enlaces (canal_id,titulo,url,agregado_por_tipo,agregado_por_id) VALUES (?,?,?,?,?)',
                (cid, titulo or url, url, tipo, uid))
    conn.commit(); conn.close()
    return jsonify({'ok':True})

# ── API COMUNICACIONES (Fase 2 — polling) ─────────────────────────────────────
@app.route('/<slug>/api/comunicaciones')
def api_comunicaciones(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if prof:
        return jsonify(comunicaciones_pendientes(slug,'profesor',prof['id']))
    aid = session.get(f'alumno_id_{slug}')
    if aid:
        return jsonify(comunicaciones_pendientes(slug,'estudiante',aid))
    return jsonify([])

@app.route('/<slug>/api/comunicaciones/count')
def api_comunicaciones_count(slug):
    require_colegio(slug)
    prof = get_profesor(slug)
    if prof:
        return jsonify({'pendientes':len(comunicaciones_pendientes(slug,'profesor',prof['id']))})
    aid = session.get(f'alumno_id_{slug}')
    if aid:
        return jsonify({'pendientes':len(comunicaciones_pendientes(slug,'estudiante',aid))})
    return jsonify({'pendientes':0})

# ── EVENTOS CALENDARIO ────────────────────────────────────────────────────────
@app.route('/<slug>/rector/comunicaciones/<int:cid>/evento')
def rector_comunicacion_evento(slug, cid):
    """Return JSON for calendar integration."""
    require_colegio(slug)
    rector = get_rector(slug)
    if not rector: return jsonify({'error': 'No autorizado'}), 403
    conn = conectar(slug)
    com = conn.execute(
        'SELECT id, titulo, fecha_programada, prioridad FROM comunicaciones WHERE id=? AND rector_id=? AND activo=1',
        (cid, rector['id'])).fetchone()
    conn.close()
    if not com: return jsonify({'error': 'No encontrada'}), 404
    return jsonify({
        'id': com['id'],
        'title': com['titulo'],
        'start': com['fecha_programada'] or datetime.today().strftime('%Y-%m-%d'),
        'className': 'event-' + com['prioridad']
    })

# ── GESTIÓN DE RECTORES (SÓLO PRINCIPAL) ───────────────────────────────────────
def require_rector_principal(slug):
    r = get_rector(slug)
    if not r: abort(401)
    if not r['es_principal']: abort(403)
    return r

@app.route('/<slug>/rector/gestion-rectores')
def rector_gestion(slug):
    r = require_rector_principal(slug)
    colegio = get_colegio(slug)
    conn = conectar(slug)
    rectores = conn.execute(
        'SELECT id, nombre, usuario, email, activo, es_principal FROM rectores ORDER BY es_principal DESC, id').fetchall()
    notif_count = notificaciones_no_leidas(slug, 'rector', r['id'])
    conn.close()
    return render_template('rector_gestion.html',
                           slug=slug, colegio=colegio, rector=r,
                           rectores=rectores, notif_count=notif_count)

@app.route('/<slug>/rector/gestion-rectores/crear', methods=['GET', 'POST'])
def rector_gestion_crear(slug):
    r = require_rector_principal(slug)
    colegio = get_colegio(slug)
    error = exito = None
    if request.method == 'POST':
        if not validar_csrf(): return 'Error de seguridad', 400
        nombre = request.form.get('nombre', '').strip()
        usuario = request.form.get('usuario', '').strip()
        password = request.form.get('password', '').strip()
        confirmar = request.form.get('confirmar_password', '').strip()
        email = request.form.get('email', '').strip()
        if not nombre or not usuario or not password:
            error = 'Completa todos los campos obligatorios.'
        elif len(password) < 6:
            error = 'Mínimo 6 caracteres para la contraseña.'
        elif password != confirmar:
            error = 'Las contraseñas no coinciden.'
        else:
            conn = conectar(slug)
            if conn.execute('SELECT 1 FROM rectores WHERE usuario=?', (usuario,)).fetchone():
                error = 'Ese usuario ya existe.'
            else:
                conn.execute(
                    'INSERT INTO rectores (nombre, usuario, password, email) VALUES (?, ?, ?, ?)',
                    (nombre, usuario, hash_pw(password), email))
                conn.commit()
                exito = f'Rector "{nombre}" creado correctamente.'
                crear_notificacion(slug, 'rector', r['id'],
                    'Nuevo rector creado', f'Se creó el rector {nombre} ({usuario}).', 'success')
            conn.close()
    return render_template('rector_gestion.html',
                           slug=slug, colegio=colegio, rector=r,
                           error=error, exito=exito, crear=True,
                           notif_count=notificaciones_no_leidas(slug, 'rector', r['id']))

@app.route('/<slug>/rector/gestion-rectores/<int:rid>/editar', methods=['GET', 'POST'])
def rector_gestion_editar(slug, rid):
    r = require_rector_principal(slug)
    colegio = get_colegio(slug)
    conn = conectar(slug)
    target = conn.execute('SELECT * FROM rectores WHERE id=?', (rid,)).fetchone()
    if not target: conn.close(); return 'Rector no encontrado', 404
    error = exito = None
    if request.method == 'POST':
        if not validar_csrf(): return 'Error de seguridad', 400
        nombre = request.form.get('nombre', '').strip()
        usuario = request.form.get('usuario', '').strip()
        password = request.form.get('password', '').strip()
        confirmar = request.form.get('confirmar_password', '').strip()
        email = request.form.get('email', '').strip()
        if not nombre or not usuario:
            error = 'Nombre y usuario son obligatorios.'
        elif password and len(password) < 6:
            error = 'Mínimo 6 caracteres.'
        elif password and password != confirmar:
            error = 'Las contraseñas no coinciden.'
        else:
            existing = conn.execute('SELECT 1 FROM rectores WHERE usuario=? AND id!=?', (usuario, rid)).fetchone()
            if existing:
                error = 'Ese nombre de usuario ya está en uso.'
            else:
                if password:
                    conn.execute(
                        'UPDATE rectores SET nombre=?, usuario=?, password=?, email=? WHERE id=?',
                        (nombre, usuario, hash_pw(password), email, rid))
                else:
                    conn.execute(
                        'UPDATE rectores SET nombre=?, usuario=?, email=? WHERE id=?',
                        (nombre, usuario, email, rid))
                conn.commit()
                exito = 'Rector actualizado correctamente.'
                target = conn.execute('SELECT * FROM rectores WHERE id=?', (rid,)).fetchone()
    conn.close()
    return render_template('rector_gestion.html',
                           slug=slug, colegio=colegio, rector=r,
                           error=error, exito=exito, editar=target,
                           notif_count=notificaciones_no_leidas(slug, 'rector', r['id']))

@app.route('/<slug>/rector/gestion-rectores/<int:rid>/toggle', methods=['POST'])
def rector_gestion_toggle(slug, rid):
    r = require_rector_principal(slug)
    if not validar_csrf(): return 'Error de seguridad', 400
    if rid == r['id']: return 'No puedes desactivarte a ti mismo.', 400
    conn = conectar(slug)
    conn.execute('UPDATE rectores SET activo = CASE WHEN activo=1 THEN 0 ELSE 1 END WHERE id=?', (rid,))
    conn.commit()
    conn.close()
    return redirect(url_for('rector_gestion', slug=slug))

@app.route('/<slug>/rector/gestion-rectores/<int:rid>/eliminar', methods=['POST'])
def rector_gestion_eliminar(slug, rid):
    r = require_rector_principal(slug)
    if not validar_csrf(): return 'Error de seguridad', 400
    if rid == r['id']: return 'No puedes eliminar tu propia cuenta.', 400
    conn = conectar(slug)
    target = conn.execute('SELECT es_principal FROM rectores WHERE id=?', (rid,)).fetchone()
    if not target: conn.close(); return 'Rector no encontrado', 404
    if target['es_principal']:
        conn.close(); return 'No puedes eliminar al Rector Principal. Transfiere el rol primero.', 400
    conn.execute('DELETE FROM rectores WHERE id=?', (rid,))
    conn.commit()
    conn.close()
    return redirect(url_for('rector_gestion', slug=slug))

@app.route('/<slug>/rector/gestion-rectores/<int:rid>/hacer-principal', methods=['POST'])
def rector_gestion_hacer_principal(slug, rid):
    r = require_rector_principal(slug)
    if not validar_csrf(): return 'Error de seguridad', 400
    if rid == r['id']: return 'Ya eres el Rector Principal.', 400
    conn = conectar(slug)
    target = conn.execute('SELECT id, activo FROM rectores WHERE id=?', (rid,)).fetchone()
    if not target: conn.close(); return 'Rector no encontrado', 404
    if not target['activo']:
        conn.close(); return 'No puedes transferir el rol a un rector inactivo.', 400
    conn.execute('UPDATE rectores SET es_principal=0 WHERE id=?', (r['id'],))
    conn.execute('UPDATE rectores SET es_principal=1 WHERE id=?', (rid,))
    conn.commit()
    conn.close()
    session[f'rector_id_{slug}'] = rid
    crear_notificacion(slug, 'rector', rid,
        'Rector Principal transferido', f'{r["nombre"]} te ha transferido el rol de Rector Principal.', 'warning')
    return redirect(url_for('rector_panel', slug=slug))

@app.route('/<slug>/directora/login', methods=['GET', 'POST'])
def directora_login(slug):
    require_colegio(slug)
    colegio = get_colegio(slug)
    error = exito = None
    ip = request.remote_addr
    if request.method == 'POST':
        if not validar_csrf():
            error = 'Error de seguridad.'
            return render_template('directora_login.html', slug=slug, colegio=colegio, error=error, exito=exito)
        bloqueado = ip_bloqueada(ip, prefijo=f'directora_{slug}')
        if bloqueado:
            error = f'Demasiados intentos. Espera {bloqueado}s.'
            return render_template('directora_login.html', slug=slug, colegio=colegio, error=error, exito=exito)
        u = request.form.get('usuario', '').strip()
        p = request.form.get('password', '').strip()
        conn = conectar(slug)
        d = conn.execute(
            'SELECT * FROM directoras WHERE usuario=? AND activo=1', (u,)).fetchone()
        conn.close()
        if d and verificar_pw(p, d['password']):
            session.clear()
            session.permanent = True
            session[f'directora_id_{slug}'] = d['id']
            limpiar_intentos(ip, prefijo=f'directora_{slug}')
            return redirect(url_for('directora_panel', slug=slug))
        registrar_fallo(ip, prefijo=f'directora_{slug}')
        error = 'Usuario o contraseña incorrectos.'
    return render_template('directora_login.html', slug=slug, colegio=colegio,
                           error=error, exito=exito)

@app.route('/<slug>/directora/registrar_directo', methods=['POST'])
def directora_registrar_directo(slug):
    if not validar_csrf():
        return 'Error de seguridad', 400
    require_colegio(slug)
    init_db(slug)
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

    # Validar código POR COLEGIO Y ROL
    codigo_colegio = get_codigo_registro(slug, 'directoras')
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
           JOIN asignaciones_materia am ON am.profesor_id=p.id AND am.jornada=ac.jornada AND am.materia=ac.materia
           WHERE ac.curso=? AND ac.jornada=? AND p.activo=1''',
        (curso, jornada, periodo, curso, jornada)).fetchall()
    materias_enviadas = set()
    profesores = []
    for p in profs_raw:
        enviado = p['cnt'] > 0
        if enviado: materias_enviadas.add(p['materia'])
        profesores.append({'materia': p['materia'], 'nombre': p['nombre'],
                           'enviado': enviado, 'fecha_envio': None})
    # Pre-fetch all notas and evaluaciones for this course/period (avoids N+1)
    aid_alumno = {a['id'] for a in alumnos}
    notas_all = conn.execute(
        '''SELECT n.aid, ac.materia, n.val FROM notas n
           JOIN actividades ac ON ac.id=n.actividad_id
           WHERE ac.curso=? AND ac.jornada=? AND COALESCE(ac.periodo,1)=?
           ORDER BY n.aid, ac.materia''',
        (curso, jornada, periodo)).fetchall()
    notas_by = {}
    for r in notas_all:
        notas_by.setdefault((r['aid'], r['materia']), []).append(r['val'])
    if aid_alumno:
        evals_all = conn.execute(
            '''SELECT aid, materia, evaluacion, autoevaluacion FROM evaluaciones
               WHERE aid IN ({}) AND COALESCE(periodo,1)=?'''.format(
                   ','.join('?' * len(aid_alumno))),
            (*aid_alumno, periodo)).fetchall()
    else:
        evals_all = []
    evals_by = {}
    for r in evals_all:
        evals_by[(r['aid'], r['materia'])] = r

    tabla = []
    for a in alumnos:
        fila = {'id': a['id'], 'nombre': a['nombre'],
                'email': a['email_acudiente'] or '', 'materias': {}, 'promedio': None}
        todos_finales = []
        for mat in lista_materias:
            notas_vals = notas_by.get((a['id'], mat), [])
            act_prom = round(sum(notas_vals) / len(notas_vals), 2) if notas_vals else None
            ev = evals_by.get((a['id'], mat))
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
    session.clear()
    return redirect(url_for('directora_login', slug=slug))

@app.route('/<slug>/directora/enviar_correos', methods=['POST'])
def directora_enviar_correos(slug):
    require_colegio(slug)
    directora = get_directora(slug)
    if not directora: return jsonify({'ok': False, 'mensaje': 'No autorizado'})
    if not validar_csrf(): return jsonify({'ok': False, 'mensaje': 'Error CSRF'})
    if not SENDGRID_API_KEY:
        return jsonify({'ok': False, 'mensaje': 'Envío de correos no configurado (falta SENDGRID_API_KEY).'})
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
            pri_hex = colegio['primary_color'] if colegio and colegio['primary_color'] else '#6c63ff'
        except (KeyError, AttributeError, TypeError):
            pri_hex = '#6c63ff'
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
            sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
            mensaje = Mail(
                from_email=EMAIL_ORIGEN,
                to_emails=email_dest,
                subject=f'Boletín de Notas — {alumno["nombre"]} · Periodo {periodo}',
                html_content=f'''<div style="font-family:sans-serif;max-width:500px;margin:0 auto;">
                    <h2 style="color:{pri_hex};">LUMINI — Boletín de Notas</h2>
                    <p>Estimado acudiente,</p>
                    <p>Adjunto encontrará el boletín de notas de <strong>{html.escape(str(alumno['nombre']))}</strong>
                       correspondiente al <strong>Periodo {periodo}</strong>.</p>
                    <p><strong>Promedio general: {prom_general}</strong></p>
                    <p style="color:#888;font-size:12px;">
                       {html.escape(str(colegio['nombre'] if colegio else slug))} · {curso} · {jornada}</p>
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

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    if app.config.get('SESSION_COOKIE_SECURE'):
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'"
    return response

@app.errorhandler(400)
def bad_request(e):
    return render_template('error.html', codigo=400, mensaje='Solicitud inválida.'), 400

@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', codigo=403, mensaje='Acceso denegado.'), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', codigo=404, mensaje='Página no encontrada.'), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return render_template('error.html', codigo=405, mensaje='Método no permitido.'), 405

@app.errorhandler(413)
def too_large(e):
    return render_template('error.html', codigo=413,
                           mensaje='El archivo es demasiado grande. Máximo permitido: 2 MB.'), 413

@app.errorhandler(429)
def too_many_requests(e):
    return render_template('error.html', codigo=429,
                           mensaje='Demasiadas solicitudes. Intenta de nuevo más tarde.'), 429

@app.errorhandler(500)
def server_error(e):
    logger.error(f'Error interno: {e}')
    return render_template('error.html', codigo=500,
                           mensaje='Error interno del servidor. Intenta de nuevo más tarde.'), 500

@app.errorhandler(502)
def bad_gateway(e):
    return render_template('error.html', codigo=502, mensaje='Servicio temporalmente no disponible.'), 502

@app.errorhandler(503)
def service_unavailable(e):
    return render_template('error.html', codigo=503, mensaje='Servicio en mantenimiento.'), 503

# ── FILTRO DÍAS RESTANTES ─────────────────────────────────────────────────────
from datetime import date as _date

@app.template_filter('dias_restantes')
def dias_restantes(fecha_str):
    try:
        fecha = _date.fromisoformat(str(fecha_str))
        return (fecha - _date.today()).days
    except Exception:
        return None

@app.template_filter('hex_to_rgb')
def hex_to_rgb(hex_color):
    """Converts #RRGGBB to 'r,g,b' string for use in rgba()."""
    h = hex_color.lstrip('#')
    if len(h) != 6:
        return '108,99,255'
    return f'{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}'

# ── ADMIN CÓDIGOS DE INVITACIÓN ──────────────────────────────────────────────
@app.route('/admin/codigos', methods=['GET', 'POST'])
@app.route('/admin/codigos/<slug>', methods=['GET', 'POST'])
def admin_codigos(slug=None):
    if not session.get('admin_auth'):
        return redirect(url_for('admin'))
    cm = conectar_master()
    error = exito = None

    if request.method == 'POST':
        if not validar_csrf():
            return 'Error de seguridad', 400
        accion = request.form.get('accion')
        if accion == 'actualizar_codigos':
            s = request.form.get('slug', '').strip()
            cod_prof = request.form.get('codigo_profesores', '').strip()
            cod_dir  = request.form.get('codigo_directoras', '').strip()
            cod_rec  = request.form.get('codigo_rectores', '').strip()
            cm.execute(
                'UPDATE colegios SET codigo_profesores=?, codigo_directoras=?, codigo_rectores=? WHERE slug=?',
                (cod_prof, cod_dir, cod_rec, s))
            cm.commit()
            exito = 'Códigos actualizados correctamente.'
            slug = s
        elif accion == 'generar_codigos':
            s = request.form.get('slug', '').strip()
            prefijo = request.form.get('prefijo', '').strip()
            if not prefijo:
                error = 'Elige un prefijo para los códigos.'
            else:
                import secrets as sec
                new_prof = f'{prefijo}_prof_{sec.token_hex(4)}'
                new_dir  = f'{prefijo}_dir_{sec.token_hex(4)}'
                new_rec  = f'{prefijo}_rec_{sec.token_hex(4)}'
                cm.execute(
                    'UPDATE colegios SET codigo_profesores=?, codigo_directoras=?, codigo_rectores=? WHERE slug=?',
                    (new_prof, new_dir, new_rec, s))
                cm.commit()
                exito = f'Códigos generados para {s}: Profesores={new_prof}, Directoras={new_dir}, Rectores={new_rec}'
                slug = s

    colegios = cm.execute('SELECT * FROM colegios ORDER BY nombre').fetchall()
    colegio_selected = None
    if slug:
        colegio_selected = cm.execute('SELECT * FROM colegios WHERE slug=?', (slug,)).fetchone()
    cm.close()
    return render_template('admin_codigos.html',
                           colegios=colegios, colegio=colegio_selected,
                           error=error, exito=exito)

# ── API PROFESORES PARA ADMIN ─────────────────────────────────────────────────
@app.route('/admin/profesores/<slug>')
def admin_ver_profesores(slug):
    if not session.get('admin_auth'):
        return jsonify({'error': 'No autorizado'}), 403
    if not get_colegio(slug):
        return jsonify({'error': 'Colegio no encontrado'}), 404
    init_db(slug)
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