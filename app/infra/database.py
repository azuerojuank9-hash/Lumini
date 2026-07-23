import logging
import os
import re as _re
import sqlite3
import threading
import time

from app.infra.config import DB_FOLDER, MASTER_DB, SCHEMA_VERSION

logger = logging.getLogger(__name__)

_cache = {}
_cache_lock = threading.Lock()
_CACHE_TTL = {'config': 60, 'cursos': 60, 'materias': 60, 'jornadas': 60, 'colegio': 300}


def _cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and entry['expires'] > time.time():
            return entry['value']
        if entry:
            del _cache[key]
    return None


def _cache_set(key, value, ttl=60):
    with _cache_lock:
        _cache[key] = {'value': value, 'expires': time.time() + ttl}


def _cache_invalidate(slug=None, prefix=None):
    with _cache_lock:
        to_del = [k for k in _cache if (slug and slug in k) or (prefix and k.startswith(prefix))]
        for k in to_del:
            del _cache[k]


def conectar_master():
    c = sqlite3.connect(MASTER_DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA foreign_keys=ON')
    return c


def db_path(slug):
    return os.path.join(DB_FOLDER, f'{slug}.db')


def conectar(slug):
    c = sqlite3.connect(db_path(slug), timeout=30)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA foreign_keys=ON')
    return c


def _recrear_si_unique_incorrecto(conn, slug, tabla, unique_deseado, sql_insert, sql_select):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (tabla,)
    ).fetchone()
    if not row:
        return False
    sql_actual = row['sql']
    m = _re.search(r'UNIQUE\s*\(([^)]+)\)', sql_actual, _re.IGNORECASE)
    if m:
        cols_actuales = [c.strip().lower() for c in m.group(1).split(',')]
        cols_deseadas = [c.strip().lower() for c in unique_deseado.strip('()').split(',')]
        if cols_actuales == cols_deseadas:
            return False
    logger.warning(f'[{slug}] Recreando tabla {tabla} (UNIQUE incorrecto)')
    conn.execute(f'ALTER TABLE {tabla} RENAME TO {tabla}_old')
    conn.execute(sql_insert)
    conn.execute(f'INSERT OR IGNORE INTO {tabla} {sql_select}')
    conn.execute(f'DROP TABLE {tabla}_old')
    conn.commit()
    return True


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


def _migrar_v11(conn, slug=None):
    conn.execute('''CREATE TABLE IF NOT EXISTS asistencia_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aid INTEGER, fecha TEXT, estado TEXT,
        UNIQUE(aid, fecha)
    )''')
    conn.execute('''INSERT OR IGNORE INTO asistencia_v2 (id, aid, fecha, estado)
        SELECT id, aid, fecha, estado FROM asistencia''')
    conn.execute('DROP TABLE asistencia')
    conn.execute('ALTER TABLE asistencia_v2 RENAME TO asistencia')
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


def _migrar_v12(conn, slug=None):
    _recrear_si_unique_incorrecto(conn, slug, 'evaluaciones',
        '(aid,profesor_id,materia,jornada,periodo)',
        '''CREATE TABLE evaluaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aid INTEGER NOT NULL, profesor_id INTEGER NOT NULL,
            materia TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT "Mañana",
            evaluacion REAL, autoevaluacion REAL, periodo INTEGER DEFAULT 1,
            UNIQUE(aid,profesor_id,materia,jornada,periodo))''',
        '''(id,aid,profesor_id,materia,jornada,evaluacion,autoevaluacion,periodo)
           SELECT id,aid,profesor_id,materia,jornada,evaluacion,autoevaluacion,
                  COALESCE(periodo,1) FROM evaluaciones_old''')
    _recrear_si_unique_incorrecto(conn, slug, 'horarios_curso',
        '(curso,jornada,dia,franja)',
        '''CREATE TABLE horarios_curso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            curso TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT "Mañana",
            dia TEXT NOT NULL, franja TEXT NOT NULL,
            num TEXT DEFAULT "", materia TEXT DEFAULT "", profesor TEXT DEFAULT "",
            UNIQUE(curso, jornada, dia, franja))''',
        'SELECT * FROM horarios_curso_old')


def _migrar_v13(conn, slug=None):
    conn.execute('''CREATE TABLE IF NOT EXISTS auditoria_notas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        rol TEXT NOT NULL,
        creado TEXT DEFAULT (datetime('now','localtime')),
        ip TEXT, curso TEXT, materia TEXT, periodo INTEGER,
        tipo_accion TEXT NOT NULL, tabla TEXT NOT NULL, registro_id INTEGER,
        aid INTEGER NOT NULL, actividad_id INTEGER, campo TEXT,
        valor_anterior TEXT, valor_nuevo TEXT, motivo TEXT
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_auditoria_notas_aid ON auditoria_notas(aid)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_auditoria_notas_curso ON auditoria_notas(curso, materia, periodo)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_auditoria_notas_curso_prof ON auditoria_notas(curso, materia, periodo, profesor_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_auditoria_notas_fecha ON auditoria_notas(creado)')


def _migrar_v14(conn, slug=None):
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='solicitudes_modificacion'")
    if cur.fetchone():
        cols = {r[1] for r in conn.execute("PRAGMA table_info(solicitudes_modificacion)").fetchall()}
        if 'slug' not in cols:
            conn.execute("DROP TABLE IF EXISTS solicitudes_modificacion")
    conn.execute('''CREATE TABLE IF NOT EXISTS solicitudes_modificacion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL, aid INTEGER NOT NULL, profesor_id INTEGER NOT NULL,
        materia TEXT NOT NULL, curso TEXT NOT NULL, jornada TEXT NOT NULL,
        periodo INTEGER NOT NULL DEFAULT 1,
        tipo TEXT NOT NULL CHECK(tipo IN ('actividad', 'evaluacion', 'autoevaluacion')),
        actividad_id INTEGER, valor_actual TEXT, valor_solicitado TEXT NOT NULL,
        motivo TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'pendiente' CHECK(estado IN ('pendiente','aprobada','rechazada')),
        aprobado_por INTEGER, fecha_solicitud TEXT DEFAULT (datetime('now','localtime')),
        fecha_respuesta TEXT
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_solicitudes_slug_estado ON solicitudes_modificacion(slug, estado)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_solicitudes_profesor ON solicitudes_modificacion(profesor_id, slug)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_solicitudes_aid ON solicitudes_modificacion(aid)')
    conn.execute("UPDATE solicitudes_modificacion SET slug=? WHERE slug IS NULL OR slug=''", (slug or '',))


def _migrar_v15(conn, slug=None):
    cur = conn.execute("PRAGMA table_info(asistencia)")
    cols = {r[1] for r in cur.fetchall()}
    for col, ddl in [
        ('observacion',   'observacion TEXT DEFAULT ""'),
        ('hora',          'hora TEXT DEFAULT ""'),
        ('usuario_tipo',  'usuario_tipo TEXT DEFAULT "profesor"'),
        ('usuario_id',    'usuario_id INTEGER DEFAULT 0'),
    ]:
        if col not in cols:
            conn.execute(f'ALTER TABLE asistencia ADD COLUMN {ddl}')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_asistencia_fecha_estado ON asistencia(fecha, estado)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_asistencia_aid_estado ON asistencia(aid, estado)')


def _migrar_v16(conn, slug=None):
    conn.execute('''CREATE TABLE IF NOT EXISTS firmas_digitales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL, usuario_tipo TEXT NOT NULL, usuario_id INTEGER NOT NULL,
        nombre TEXT NOT NULL, documento_tipo TEXT NOT NULL, documento_id INTEGER NOT NULL,
        hash_documento TEXT NOT NULL, firma_hash TEXT NOT NULL,
        metodo TEXT DEFAULT 'hmac-sha256', ip TEXT DEFAULT '', user_agent TEXT DEFAULT '',
        creado TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_firmas_doc ON firmas_digitales(documento_tipo, documento_id)')
    conn.execute('''CREATE TABLE IF NOT EXISTS enterprise_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL,
        usuario_id INTEGER, usuario_tipo TEXT DEFAULT '', accion TEXT NOT NULL,
        categoria TEXT DEFAULT '', descripcion TEXT DEFAULT '', tabla TEXT DEFAULT '',
        registro_id INTEGER, valor_anterior TEXT, valor_nuevo TEXT, ip TEXT DEFAULT '',
        user_agent TEXT DEFAULT '', dispositivo TEXT DEFAULT '', navegador TEXT DEFAULT '',
        sesion_id TEXT DEFAULT '', nivel TEXT DEFAULT 'info',
        creado TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_enterprise_audit_slug ON enterprise_audit_log(slug, creado)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_enterprise_audit_accion ON enterprise_audit_log(accion)')
    conn.execute('''CREATE TABLE IF NOT EXISTS observador_registros (
        id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL, aid INTEGER NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('positivo','llamado','compromiso','seguimiento')),
        texto TEXT NOT NULL, docente TEXT DEFAULT '', materia TEXT DEFAULT '',
        estado TEXT DEFAULT 'pendiente' CHECK(estado IN ('pendiente','aprobado','rechazado')),
        aprobado_por_tipo TEXT, aprobado_por_id INTEGER,
        fecha TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_observador_aid ON observador_registros(aid)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_observador_tipo ON observador_registros(tipo)')
    conn.execute('''CREATE TABLE IF NOT EXISTS expediente_documentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL, aid INTEGER NOT NULL,
        tipo TEXT NOT NULL, nombre TEXT NOT NULL, archivo TEXT DEFAULT '',
        descripcion TEXT DEFAULT '', subido_por_tipo TEXT DEFAULT 'rector',
        subido_por_id INTEGER DEFAULT 0,
        fecha TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_expediente_aid ON expediente_documentos(aid)')
    conn.execute('''CREATE TABLE IF NOT EXISTS eventos_calendario (
        id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL,
        tipo TEXT NOT NULL DEFAULT 'evento', titulo TEXT NOT NULL,
        descripcion TEXT DEFAULT '', fecha_inicio TEXT NOT NULL, fecha_fin TEXT,
        todo_el_dia INTEGER DEFAULT 1, curso TEXT DEFAULT '',
        creado_por_tipo TEXT DEFAULT 'rector', creado_por_id INTEGER DEFAULT 0,
        color TEXT DEFAULT '#6c63ff', fecha_creacion TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_eventos_fecha ON eventos_calendario(slug, fecha_inicio)')
    conn.execute('''CREATE TABLE IF NOT EXISTS pagos_estructura (
        id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL,
        alumno_id INTEGER NOT NULL, concepto TEXT NOT NULL, monto REAL NOT NULL,
        descuento REAL DEFAULT 0, pagado REAL DEFAULT 0,
        estado TEXT DEFAULT 'pendiente' CHECK(estado IN ('pendiente','pagado','parcial','anulado')),
        fecha_vencimiento TEXT, fecha_pago TEXT, metodo_pago TEXT DEFAULT '',
        referencia TEXT DEFAULT '', notas TEXT DEFAULT '',
        creado TEXT DEFAULT (datetime('now','localtime')),
        actualizado TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_pagos_alumno ON pagos_estructura(alumno_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_pagos_estado ON pagos_estructura(estado)')


def _migrar_v17(conn, slug=None):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(actividades)").fetchall()}
    for col, ddl in {
        'tipo': "ALTER TABLE actividades ADD COLUMN tipo TEXT DEFAULT 'taller'",
        'peso': "ALTER TABLE actividades ADD COLUMN peso REAL",
        'categoria': "ALTER TABLE actividades ADD COLUMN categoria TEXT DEFAULT 'evaluacion'",
        'fecha_limite': "ALTER TABLE actividades ADD COLUMN fecha_limite TEXT",
        'hora_limite': "ALTER TABLE actividades ADD COLUMN hora_limite TEXT",
        'descripcion': "ALTER TABLE actividades ADD COLUMN descripcion TEXT DEFAULT ''",
        'observaciones': "ALTER TABLE actividades ADD COLUMN observaciones TEXT DEFAULT ''",
        'estado_act': "ALTER TABLE actividades ADD COLUMN estado_act TEXT DEFAULT 'publicada'",
        'competencia': "ALTER TABLE actividades ADD COLUMN competencia TEXT DEFAULT ''",
        'entrega_digital': "ALTER TABLE actividades ADD COLUMN entrega_digital INTEGER DEFAULT 0",
        'adjuntos': "ALTER TABLE actividades ADD COLUMN adjuntos TEXT DEFAULT '[]'",
        'integration': "ALTER TABLE actividades ADD COLUMN integration TEXT DEFAULT ''",
    }.items():
        if col not in cols:
            conn.execute(ddl)
    conn.execute('''CREATE TABLE IF NOT EXISTS entregas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, actividad_id INTEGER NOT NULL,
        alumno_id INTEGER NOT NULL, fecha_entrega TEXT DEFAULT (datetime('now','localtime')),
        archivos TEXT DEFAULT '[]', comentario TEXT DEFAULT '', estado TEXT DEFAULT 'pendiente',
        calificacion REAL, retroalimentacion TEXT DEFAULT '', calificado_por INTEGER,
        fecha_calificacion TEXT, UNIQUE(actividad_id, alumno_id)
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_entregas_actividad ON entregas(actividad_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_entregas_alumno ON entregas(alumno_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_entregas_estado ON entregas(estado)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_actividades_tipo ON actividades(tipo)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_actividades_estado ON actividades(estado_act)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_actividades_fecha_limite ON actividades(fecha_limite)')


def _migrar_v18(conn, slug=None):
    conn.execute('''CREATE TABLE IF NOT EXISTS plantillas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, profesor_id INTEGER NOT NULL,
        nombre TEXT NOT NULL, tipo TEXT DEFAULT 'tarea', peso REAL DEFAULT 10,
        descripcion TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')


def _migrar_v19(conn, slug=None):
    conn.execute('''CREATE TABLE IF NOT EXISTS historial_academico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, alumno_id INTEGER NOT NULL,
        curso TEXT NOT NULL, jornada TEXT DEFAULT '', periodo INTEGER DEFAULT 1,
        promedio_final REAL DEFAULT 0, estado TEXT DEFAULT 'cursando',
        observaciones TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS padres (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE, pin TEXT NOT NULL, telefono TEXT DEFAULT '',
        activo INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS alumno_padre (
        id INTEGER PRIMARY KEY AUTOINCREMENT, alumno_id INTEGER NOT NULL,
        padre_id INTEGER NOT NULL, parentesco TEXT DEFAULT ''
    )''')


def _migrar_v20(conn, slug=None):
    conn.execute('''CREATE TABLE IF NOT EXISTS matriculas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, alumno_id INTEGER DEFAULT 0,
        nombre TEXT NOT NULL, documento TEXT DEFAULT '', email TEXT DEFAULT '',
        telefono TEXT DEFAULT '', curso_solicitado TEXT DEFAULT '',
        jornada TEXT DEFAULT 'mañana', sede TEXT DEFAULT '',
        estado TEXT DEFAULT 'pendiente', documentos TEXT DEFAULT '',
        observaciones TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS tesoreria_facturas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, alumno_id INTEGER DEFAULT 0,
        concepto TEXT NOT NULL, monto REAL DEFAULT 0, descuento REAL DEFAULT 0,
        estado TEXT DEFAULT 'pendiente', fecha_emision DATE DEFAULT (date('now')),
        fecha_vencimiento DATE DEFAULT (date('now','+30 days')), fecha_pago DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS tesoreria_pagos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, factura_id INTEGER NOT NULL,
        monto REAL NOT NULL, metodo TEXT DEFAULT 'efectivo', referencia TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

def _migrar_v21(conn, slug=None):
    conn.execute('CREATE INDEX IF NOT EXISTS idx_alumno_padre_padre ON alumno_padre(padre_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_alumno_padre_alumno ON alumno_padre(alumno_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_observador_registros_aid ON observador_registros(aid)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_eventos_curso ON eventos_calendario(curso)')

MIGRACIONES = {
    6:  _migrar_v6,
    7:  _migrar_v7,
    8:  _migrar_v8,
    9:  _migrar_v9,
    10: _migrar_v10,
    11: _migrar_v11,
    12: _migrar_v12,
    13: _migrar_v13,
    14: _migrar_v14,
    15: _migrar_v15,
    16: _migrar_v16,
    17: _migrar_v17,
    18: _migrar_v18,
    19: _migrar_v19,
    20: _migrar_v20,
    21: _migrar_v21,
}


def get_codigo_registro(slug, rol=None):
    c = get_colegio(slug)
    if not c:
        return ''
    if rol == 'profesores':
        val = c['codigo_profesores'] or c['codigo_registro'] or ''
    elif rol == 'directoras':
        val = c['codigo_directoras'] or c['codigo_registro'] or ''
    elif rol == 'rectores':
        val = c['codigo_rectores'] or c['codigo_registro'] or ''
    else:
        val = c['codigo_registro'] or ''
    return val


def get_colegio(slug):
    key = f'col_{slug}'
    cached = _cache_get(key)
    if cached:
        return cached
    conn = conectar_master()
    row = conn.execute('SELECT * FROM colegios WHERE slug=?', (slug,)).fetchone()
    conn.close()
    if row:
        val = dict(row)
        _cache_set(key, val, ttl=_CACHE_TTL['colegio'])
        return val
    return None


def config_get(slug):
    key = f'cfg_{slug}'
    cached = _cache_get(key)
    if cached:
        return cached
    conn = conectar(slug)
    cfg = conn.execute('SELECT * FROM config_institucion WHERE slug=?', (slug,)).fetchone()
    conn.close()
    if cfg:
        _cache_set(key, dict(cfg), ttl=_CACHE_TTL['config'])
        return dict(cfg)
    return {}


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
        try:
            conn.execute(f'ALTER TABLE colegios ADD COLUMN {col}')
        except sqlite3.OperationalError:
            logger.debug(f'Columna ya existe en colegios: {col.split()[0]}')
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
        _recrear_si_unique_incorrecto(conn, slug, 'evaluaciones',
            '(aid,profesor_id,materia,jornada,periodo)',
            '''CREATE TABLE evaluaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aid INTEGER NOT NULL, profesor_id INTEGER NOT NULL,
                materia TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT "Mañana",
                evaluacion REAL, autoevaluacion REAL, periodo INTEGER DEFAULT 1,
                UNIQUE(aid,profesor_id,materia,jornada,periodo))''',
            '''(id,aid,profesor_id,materia,jornada,evaluacion,autoevaluacion,periodo)
               SELECT id,aid,profesor_id,materia,jornada,evaluacion,autoevaluacion,
                      COALESCE(periodo,1) FROM evaluaciones_old''')
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
        _recrear_si_unique_incorrecto(conn, slug, 'horarios_curso',
            '(curso,jornada,dia,franja)',
            '''CREATE TABLE horarios_curso (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                curso TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT "Mañana",
                dia TEXT NOT NULL, franja TEXT NOT NULL,
                num TEXT DEFAULT "", materia TEXT DEFAULT "", profesor TEXT DEFAULT "",
                UNIQUE(curso, jornada, dia, franja))''',
            'SELECT * FROM horarios_curso_old')
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
            aid INTEGER, fecha TEXT, estado TEXT,
            UNIQUE(aid, fecha))''',
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
            titulo TEXT NOT NULL, contenido TEXT NOT NULL,
            destinatario_tipo TEXT NOT NULL, destinatario_valor TEXT DEFAULT '',
            prioridad TEXT NOT NULL DEFAULT 'normal',
            estado TEXT NOT NULL DEFAULT 'borrador',
            fecha_creacion TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            fecha_programada TEXT DEFAULT NULL,
            fecha_publicacion TEXT DEFAULT NULL,
            activo INTEGER DEFAULT 1)''',
        '''CREATE TABLE IF NOT EXISTS comunicaciones_leidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comunicacion_id INTEGER NOT NULL,
            usuario_tipo TEXT NOT NULL, usuario_id INTEGER NOT NULL,
            leido INTEGER DEFAULT 0,
            fecha_lectura TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(comunicacion_id, usuario_tipo, usuario_id))''',
        '''CREATE TABLE IF NOT EXISTS notificaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_tipo TEXT NOT NULL, usuario_id INTEGER NOT NULL,
            titulo TEXT NOT NULL, mensaje TEXT DEFAULT '',
            tipo TEXT NOT NULL DEFAULT 'info', link TEXT DEFAULT '',
            leida INTEGER DEFAULT 0,
            fecha_creacion TEXT NOT NULL DEFAULT (datetime('now','localtime')))''',
        '''CREATE TABLE IF NOT EXISTS canales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL, rector_id INTEGER NOT NULL,
            tipo TEXT NOT NULL, nombre TEXT NOT NULL,
            descripcion TEXT DEFAULT '', curso TEXT DEFAULT '',
            materia TEXT DEFAULT '', activo INTEGER DEFAULT 1,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime')))''',
        '''CREATE TABLE IF NOT EXISTS canal_miembros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canal_id INTEGER NOT NULL, usuario_tipo TEXT NOT NULL,
            usuario_id INTEGER NOT NULL,
            fecha_ingreso TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(canal_id, usuario_tipo, usuario_id))''',
        '''CREATE TABLE IF NOT EXISTS mensajes_canal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canal_id INTEGER NOT NULL, usuario_tipo TEXT NOT NULL,
            usuario_id INTEGER NOT NULL, mensaje TEXT NOT NULL,
            fecha TEXT DEFAULT (datetime('now','localtime')),
            editado INTEGER DEFAULT 0)''',
        '''CREATE TABLE IF NOT EXISTS mensajes_leidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mensaje_id INTEGER NOT NULL, usuario_tipo TEXT NOT NULL,
            usuario_id INTEGER NOT NULL,
            fecha_lectura TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(mensaje_id, usuario_tipo, usuario_id))''',
        '''CREATE TABLE IF NOT EXISTS periodos_estado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo INTEGER NOT NULL UNIQUE,
            estado TEXT NOT NULL DEFAULT 'abierto',
            fecha_apertura TEXT, fecha_cierre TEXT,
            abierto_por INTEGER, cerrado_por INTEGER)''',
        '''CREATE TABLE IF NOT EXISTS mensajes_archivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mensaje_id INTEGER, canal_id INTEGER NOT NULL,
            usuario_tipo TEXT NOT NULL, usuario_id INTEGER NOT NULL,
            nombre_original TEXT NOT NULL, nombre_archivo TEXT NOT NULL,
            tipo_mime TEXT NOT NULL, tamano INTEGER NOT NULL,
            es_imagen INTEGER DEFAULT 0, ancho INTEGER, alto INTEGER,
            fecha TEXT DEFAULT (datetime('now','localtime')))''',
        '''CREATE TABLE IF NOT EXISTS mensajes_reacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mensaje_id INTEGER NOT NULL, usuario_tipo TEXT NOT NULL,
            usuario_id INTEGER NOT NULL, reaccion TEXT NOT NULL,
            fecha TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(mensaje_id, usuario_tipo, usuario_id, reaccion))''',
        '''CREATE TABLE IF NOT EXISTS mensajes_fijados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canal_id INTEGER NOT NULL, mensaje_id INTEGER NOT NULL,
            fijado_por_tipo TEXT NOT NULL, fijado_por_id INTEGER NOT NULL,
            fecha TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(canal_id, mensaje_id))''',
        '''CREATE TABLE IF NOT EXISTS canal_enlaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canal_id INTEGER NOT NULL, titulo TEXT, url TEXT NOT NULL,
            agregado_por_tipo TEXT NOT NULL, agregado_por_id INTEGER NOT NULL,
            fecha TEXT DEFAULT (datetime('now','localtime')))''',
        '''CREATE TABLE IF NOT EXISTS canal_actividad (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canal_id INTEGER NOT NULL, usuario_tipo TEXT NOT NULL,
            usuario_id INTEGER NOT NULL, estado TEXT DEFAULT 'online',
            ultima_vista TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(canal_id, usuario_tipo, usuario_id))''',
    ]
    for s in stmts:
        try:
            conn.execute(s)
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
        try:
            conn.execute(stmt)
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
        'CREATE INDEX IF NOT EXISTS idx_alumnos_curso_jornada ON alumnos(curso, jornada, activo)',
        'CREATE INDEX IF NOT EXISTS idx_asistencia_aid_fecha ON asistencia(aid, fecha)',
        'CREATE INDEX IF NOT EXISTS idx_compromisos_materia ON compromisos(materia, curso, jornada)',
        'CREATE INDEX IF NOT EXISTS idx_horarios_materia ON horarios_curso(materia, jornada, dia)',
        'CREATE INDEX IF NOT EXISTS idx_notificaciones_usuario ON notificaciones(usuario_tipo, usuario_id, leida)',
        'CREATE INDEX IF NOT EXISTS idx_comunicaciones_rector ON comunicaciones(rector_id, activo)',
        'CREATE INDEX IF NOT EXISTS idx_asignaciones_curso_prof ON asignaciones_curso(profesor_id, materia, jornada)',
        'CREATE INDEX IF NOT EXISTS idx_canal_miembros_usuario ON canal_miembros(usuario_tipo, usuario_id)',
        'CREATE INDEX IF NOT EXISTS idx_canales_slug ON canales(slug)',
        'CREATE INDEX IF NOT EXISTS idx_evaluaciones_aid_periodo ON evaluaciones(aid, periodo)',
        'CREATE INDEX IF NOT EXISTS idx_actividades_curso ON actividades(curso, jornada, periodo)',
        'CREATE INDEX IF NOT EXISTS idx_asignaciones_materia_prof ON asignaciones_materia(profesor_id)',
        'CREATE INDEX IF NOT EXISTS idx_profesores_usuario ON profesores(usuario, activo)',
        'CREATE INDEX IF NOT EXISTS idx_directoras_usuario ON directoras(usuario, activo)',
        'CREATE INDEX IF NOT EXISTS idx_rectores_usuario ON rectores(usuario, activo)',
        'CREATE INDEX IF NOT EXISTS idx_comunicaciones_leidas_user ON comunicaciones_leidas(usuario_tipo, usuario_id, leido)',
        'CREATE INDEX IF NOT EXISTS idx_periodos_estado_periodo ON periodos_estado(periodo)',
        'CREATE INDEX IF NOT EXISTS idx_config_institucion_slug ON config_institucion(slug)',
        'CREATE INDEX IF NOT EXISTS idx_alumnos_id_curso ON alumnos(id, curso)',
        'CREATE INDEX IF NOT EXISTS idx_comunicaciones_estado ON comunicaciones(rector_id, activo, estado)',
        'CREATE INDEX IF NOT EXISTS idx_ml_mensaje_tipo ON mensajes_leidos(mensaje_id, usuario_tipo, usuario_id)',
        'CREATE INDEX IF NOT EXISTS idx_obs_aid_materia ON observaciones(aid, materia)',
        'CREATE INDEX IF NOT EXISTS idx_comunicaciones_rector_fecha ON comunicaciones(rector_id, activo, fecha_creacion)',
        'CREATE INDEX IF NOT EXISTS idx_audit_log_tabla ON audit_log(tabla)',
        'CREATE INDEX IF NOT EXISTS idx_asistencia_fecha ON asistencia(fecha)',
        'CREATE INDEX IF NOT EXISTS idx_actividades_prof_periodo ON actividades(profesor_id, materia, jornada, curso, periodo)',
        'CREATE INDEX IF NOT EXISTS idx_solicitudes_fecha ON solicitudes_modificacion(fecha_solicitud)',
    ]
    for idx in indexes:
        try:
            conn.execute(idx)
        except sqlite3.OperationalError as e:
            logger.warning(f'init_db index: {e}')
    conn.commit()
    _ejecutar_migraciones(slug, conn)
    conn.close()
    migrar_db(slug)
