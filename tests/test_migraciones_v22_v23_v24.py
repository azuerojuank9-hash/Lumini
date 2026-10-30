"""Regresiones del orden de inicialización y de las migraciones v22-v24.

Fallo histórico cubierto aquí: ``init_db`` ejecutaba ``_ejecutar_migraciones``
(v22/v23) antes de ``migrar_db(slug)``, que es precisamente quien agrega las
columnas legacy ``alumnos.jornada`` y ``alumnos.pin``. En una base antigua
(``schema_meta`` en 21) la inicialización fallaba con
``no such column: jornada`` / ``no such column: pin`` y bloqueaba el login.

Todos los escenarios usan bases temporales aisladas. No se toca ninguna base
real.
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('ENV', 'development')

import pytest  # noqa: E402

import app.infra.database as db  # noqa: E402


# ── Construcción de una base "antigua" (v21) ────────────────────────────────

_DDL_V21 = """
CREATE TABLE schema_meta (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE config_institucion (
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
);
CREATE TABLE materias (
    id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL,
    nombre TEXT NOT NULL, activo INTEGER DEFAULT 1,
    UNIQUE(slug, nombre)
);
CREATE TABLE profesores (
    id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
    usuario TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
    activo INTEGER DEFAULT 1, email TEXT DEFAULT '', telefono TEXT DEFAULT '',
    pregunta_secreta TEXT DEFAULT '', respuesta_secreta TEXT DEFAULT ''
);
CREATE TABLE actividades (
    id INTEGER PRIMARY KEY AUTOINCREMENT, profesor_id INTEGER NOT NULL,
    materia TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT 'Mañana',
    curso TEXT NOT NULL, nombre TEXT NOT NULL,
    orden INTEGER DEFAULT 0, periodo INTEGER DEFAULT 1
);
CREATE TABLE asignaciones_materia (
    id INTEGER PRIMARY KEY AUTOINCREMENT, profesor_id INTEGER NOT NULL,
    materia TEXT NOT NULL, jornada TEXT NOT NULL,
    UNIQUE(profesor_id, materia, jornada)
);
CREATE TABLE asignaciones_curso (
    id INTEGER PRIMARY KEY AUTOINCREMENT, profesor_id INTEGER NOT NULL,
    materia TEXT NOT NULL, jornada TEXT NOT NULL, curso TEXT NOT NULL,
    UNIQUE(profesor_id, materia, jornada, curso)
);
CREATE TABLE evaluaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT, aid INTEGER NOT NULL,
    profesor_id INTEGER NOT NULL, materia TEXT NOT NULL,
    jornada TEXT NOT NULL DEFAULT 'Mañana', evaluacion REAL,
    autoevaluacion REAL, periodo INTEGER DEFAULT 1,
    UNIQUE(aid, profesor_id, materia, jornada, periodo)
);
CREATE TABLE compromisos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, fecha TEXT,
    materia TEXT, curso TEXT, jornada TEXT DEFAULT 'Mañana'
);
CREATE TABLE horarios_curso (
    id INTEGER PRIMARY KEY AUTOINCREMENT, curso TEXT NOT NULL,
    jornada TEXT NOT NULL DEFAULT 'Mañana', dia TEXT NOT NULL,
    franja TEXT NOT NULL, num TEXT DEFAULT '', materia TEXT DEFAULT '',
    profesor TEXT DEFAULT '', UNIQUE(curso, jornada, dia, franja)
);
CREATE TABLE directoras (
    id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
    usuario TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
    curso TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT 'Mañana',
    email TEXT DEFAULT '', activo INTEGER DEFAULT 1,
    pregunta_secreta TEXT DEFAULT '', respuesta_secreta TEXT DEFAULT ''
);
CREATE TABLE rectores (
    id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
    usuario TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
    email TEXT DEFAULT '', activo INTEGER DEFAULT 1,
    es_principal INTEGER DEFAULT 0,
    pregunta_secreta TEXT DEFAULT '', respuesta_secreta TEXT DEFAULT ''
);
CREATE TABLE comunicaciones_leidas (
    id INTEGER PRIMARY KEY AUTOINCREMENT, comunicacion_id INTEGER NOT NULL,
    usuario_tipo TEXT NOT NULL, usuario_id INTEGER NOT NULL,
    leido INTEGER DEFAULT 0,
    fecha_lectura TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(comunicacion_id, usuario_tipo, usuario_id)
);
"""

_DDL_ALUMNOS_CON_JORNADA = """
CREATE TABLE alumnos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
    curso TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT 'Mañana',
    num_curso INTEGER DEFAULT 0, activo INTEGER DEFAULT 1,
    email_acudiente TEXT DEFAULT '', pin TEXT DEFAULT ''
);
"""

_DDL_ALUMNOS_SIN_COLUMNAS = """
CREATE TABLE alumnos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
    curso TEXT NOT NULL, num_curso INTEGER DEFAULT 0,
    activo INTEGER DEFAULT 1, email_acudiente TEXT DEFAULT ''
);
"""


def _crear_bd_v21(path, con_jornada=False, con_pin=False):
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_DDL_V21)
        conn.executescript(
            _DDL_ALUMNOS_CON_JORNADA if (con_jornada or con_pin)
            else _DDL_ALUMNOS_SIN_COLUMNAS)
        if con_jornada and not con_pin:
            conn.execute('ALTER TABLE alumnos DROP COLUMN pin')
        if con_pin and not con_jornada:
            conn.execute('ALTER TABLE alumnos DROP COLUMN jornada')
        conn.execute('INSERT INTO schema_meta (version) VALUES (21)')
        conn.execute(
            "INSERT INTO config_institucion (slug, jornadas_json) "
            "VALUES ('viejo', '[\"Mañana\", \"Tarde\"]')")
        conn.execute(
            "INSERT INTO alumnos (nombre, curso, num_curso, activo) VALUES "
            "('Ana', '5A', 1, 1), ('Beto', '5A', 2, 1)")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def slug_viejo(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_FOLDER', str(tmp_path))
    slug = 'viejo'
    _crear_bd_v21(db.db_path(slug), con_jornada=False, con_pin=False)
    yield slug
    # La sesión de pytest es la única dueña de tmp_path; no se toca nada real.


def _cols(conn, tabla):
    return [r[1] for r in conn.execute(f'PRAGMA table_info({tabla})').fetchall()]


# ── Escenario crítico: BD antigua sin jornada ni pin ────────────────────────

def test_init_db_bd_antigua_sin_jornada_ni_pin(slug_viejo):
    """No debe fallar: migrar_db agrega las columnas antes de v22/v23."""
    db.init_db(slug_viejo)

    conn = db.conectar(slug_viejo)
    try:
        assert 'jornada' in _cols(conn, 'alumnos')
        assert 'pin' in _cols(conn, 'alumnos')
        assert conn.execute(
            'SELECT MAX(version) v FROM schema_meta').fetchone()['v'] == 24
    finally:
        conn.close()


def test_init_db_bd_antigua_conserva_datos_y_puebla_catalogos(slug_viejo):
    db.init_db(slug_viejo)

    conn = db.conectar(slug_viejo)
    try:
        alumnos = conn.execute(
            'SELECT nombre, curso, jornada FROM alumnos ORDER BY id').fetchall()
        assert [(r['nombre'], r['curso']) for r in alumnos] == [
            ('Ana', '5A'), ('Beto', '5A')]
        # jornada se agrega con el default seguro.
        assert all(r['jornada'] == 'Mañana' for r in alumnos)

        # v23 sincroniza identidad sin borrar ni duplicar alumnos.
        assert conn.execute(
            'SELECT COUNT(*) c FROM estudiantes').fetchone()['c'] == 2
        # v22 puebla el catálogo de cursos desde los datos legacy.
        assert conn.execute(
            "SELECT COUNT(*) c FROM cursos WHERE nombre='5A'").fetchone()['c'] == 1
        # v24 crea la estructura de matrícula.
        assert 'estado' in _cols(conn, 'anio_lectivo')
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='matricula_academica'").fetchone() is not None
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    finally:
        conn.close()


def test_init_db_idempotente_dos_veces(slug_viejo):
    db.init_db(slug_viejo)
    conn = db.conectar(slug_viejo)
    try:
        antes = {
            'alumnos': conn.execute('SELECT COUNT(*) c FROM alumnos').fetchone()['c'],
            'estudiantes': conn.execute('SELECT COUNT(*) c FROM estudiantes').fetchone()['c'],
            'cursos': conn.execute('SELECT COUNT(*) c FROM cursos').fetchone()['c'],
        }
    finally:
        conn.close()

    db.init_db(slug_viejo)

    conn = db.conectar(slug_viejo)
    try:
        despues = {
            'alumnos': conn.execute('SELECT COUNT(*) c FROM alumnos').fetchone()['c'],
            'estudiantes': conn.execute('SELECT COUNT(*) c FROM estudiantes').fetchone()['c'],
            'cursos': conn.execute('SELECT COUNT(*) c FROM cursos').fetchone()['c'],
        }
        assert conn.execute(
            'SELECT MAX(version) v FROM schema_meta').fetchone()['v'] == 24
    finally:
        conn.close()
    assert despues == antes


@pytest.mark.parametrize('con_jornada,con_pin', [(True, False), (False, True), (True, True)])
def test_init_db_bd_antigua_variantes_de_columnas(tmp_path, monkeypatch, con_jornada, con_pin):
    monkeypatch.setattr(db, 'DB_FOLDER', str(tmp_path))
    slug = 'variante'
    _crear_bd_v21(db.db_path(slug), con_jornada=con_jornada, con_pin=con_pin)
    db.init_db(slug)
    conn = db.conectar(slug)
    try:
        assert 'jornada' in _cols(conn, 'alumnos')
        assert 'pin' in _cols(conn, 'alumnos')
        assert conn.execute(
            'SELECT MAX(version) v FROM schema_meta').fetchone()['v'] == 24
    finally:
        conn.close()


# ── v24 defensiva: estructura incompleta con filas legacy ───────────────────

def _crear_bd_v23_incompleta(path):
    _crear_bd_v21(path)
    conn = sqlite3.connect(path)
    try:
        # Simula una base que ya pasó v22/v23 pero cuya anio_lectivo tiene filas
        # y todavía no recibió estado ni matricula_academica (v24 pendiente).
        conn.execute(
            'CREATE TABLE anio_lectivo ('
            'id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL, '
            'nombre TEXT NOT NULL, inicio TEXT, fin TEXT, '
            'vigente INTEGER DEFAULT 0, activo INTEGER DEFAULT 1, '
            'UNIQUE(slug, nombre))')
        conn.execute(
            'CREATE TABLE estudiantes ('
            'id INTEGER PRIMARY KEY, slug TEXT NOT NULL, nombre TEXT NOT NULL, '
            'pin_legacy TEXT NULL)')
        conn.execute(
            'CREATE TABLE jornadas ('
            'id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL, '
            'nombre TEXT NOT NULL, orden INTEGER DEFAULT 0, '
            'activo INTEGER DEFAULT 1, UNIQUE(slug, nombre))')
        conn.execute(
            'CREATE TABLE cursos ('
            'id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL, '
            'sede_id INTEGER NOT NULL, jornada_id INTEGER NOT NULL, '
            'grado_id INTEGER, nombre TEXT NOT NULL, activo INTEGER DEFAULT 1, '
            'UNIQUE(sede_id, jornada_id, nombre))')
        conn.execute(
            "INSERT INTO anio_lectivo (slug, nombre, vigente) VALUES ('viejo', '2025', 1)")
        conn.execute("UPDATE schema_meta SET version=23")
        conn.commit()
    finally:
        conn.close()


def test_v24_aborta_controladamente_sin_modificar_estructura(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_FOLDER', str(tmp_path))
    slug = 'incompleta'
    _crear_bd_v23_incompleta(db.db_path(slug))

    with pytest.raises(RuntimeError):
        db.init_db(slug)

    conn = db.conectar(slug)
    try:
        # v24 hizo rollback: no agregó estado ni creó matricula_academica.
        assert 'estado' not in _cols(conn, 'anio_lectivo')
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='matricula_academica'").fetchone() is None
        # El dato legacy no se perdió ni se alteró.
        fila = conn.execute('SELECT nombre, vigente FROM anio_lectivo').fetchone()
        assert (fila['nombre'], fila['vigente']) == ('2025', 1)
        # La migración no se marcó como aplicada.
        assert conn.execute(
            'SELECT MAX(version) v FROM schema_meta').fetchone()['v'] == 23
    finally:
        conn.close()


# ── Base nueva ───────────────────────────────────────────────────────────────

def test_init_db_base_nueva_crea_esquema_v24(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_FOLDER', str(tmp_path))
    slug = 'nueva'
    db.init_db(slug)
    conn = db.conectar(slug)
    try:
        assert conn.execute(
            'SELECT MAX(version) v FROM schema_meta').fetchone()['v'] == 24
        for tabla in ('alumnos', 'estudiantes', 'cursos', 'jornadas',
                      'anio_lectivo', 'matricula_academica'):
            assert conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (tabla,)).fetchone() is not None
        assert 'estado' in _cols(conn, 'anio_lectivo')
        assert _cols(conn, 'alumnos')[:0] == []
        assert {'jornada', 'pin'} <= set(_cols(conn, 'alumnos'))
    finally:
        conn.close()
