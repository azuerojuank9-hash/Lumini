"""F2.4 — Estructura física de año lectivo y matrícula académica.

Tests de restricciones sobre una BD temporal aislada usando el DDL real de
_migrar_v24 (verifica CHECKs, FKs RESTRICT, índice único parcial de activas y
de candidatos). Validación estructural A-L como solo-lectura sobre las BD reales
autorizadas (testcolegio, colegio-qa, test-school).
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'

import pytest

from flask_app import _migrar_v24, db_path  # noqa: E402

SLUGS_REALES = ('testcolegio', 'colegio-qa', 'test-school')

EXPECTED_COLS = [
    'id', 'slug', 'estudiante_id', 'anio_lectivo_id', 'curso_id', 'num_curso',
    'estado', 'fecha_inicio', 'fecha_fin', 'motivo_retiro', 'observaciones',
    'created_at', 'updated_at',
]

EXPECTED_IDX = [
    'idx_ma_estudiante_anio', 'uq_ma_una_activa_por_anio', 'idx_ma_anio_estado',
    'idx_ma_curso_activo', 'idx_ma_curso_num', 'uq_ma_un_candidato_por_estudiante',
]

FORBIDDEN_IDX = ['idx_ma_slug', 'idx_ma_activa_est']


def _crear_prerequisitos(conn):
    conn.execute('''CREATE TABLE anio_lectivo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL, nombre TEXT NOT NULL, inicio TEXT, fin TEXT,
        vigente INTEGER DEFAULT 0, activo INTEGER DEFAULT 1,
        UNIQUE(slug, nombre))''')
    conn.execute('''CREATE TABLE estudiantes (
        id INTEGER PRIMARY KEY, slug TEXT NOT NULL, nombre TEXT NOT NULL,
        pin_legacy TEXT NULL)''')
    conn.execute('''CREATE TABLE cursos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL,
        sede_id INTEGER NOT NULL, jornada_id INTEGER NOT NULL,
        grado_id INTEGER, nombre TEXT NOT NULL, activo INTEGER DEFAULT 1,
        UNIQUE(sede_id, jornada_id, nombre))''')
    conn.execute('''CREATE TABLE jornadas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL,
        nombre TEXT NOT NULL, orden INTEGER DEFAULT 0, activo INTEGER DEFAULT 1,
        UNIQUE(slug, nombre))''')


@pytest.fixture
def temp_db():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    _crear_prerequisitos(conn)
    _migrar_v24(conn, 'test_f24')
    yield conn
    conn.close()


def _semilla(conn):
    conn.execute("INSERT INTO estudiantes (id, slug, nombre) VALUES (1, 's', 'Est Uno'), (2, 's', 'Est Dos')")
    conn.execute("INSERT INTO jornadas (id, slug, nombre) VALUES (1, 's', 'Mañana')")
    conn.execute("INSERT INTO cursos (id, slug, sede_id, jornada_id, nombre) VALUES "
                 "(1, 's', 1, 1, 'Primero A')")
    conn.execute("INSERT INTO anio_lectivo (id, slug, nombre, estado) VALUES "
                 "(1, 's', '2026', 'activo')")
    conn.execute("INSERT INTO anio_lectivo (id, slug, nombre, estado) VALUES "
                 "(2, 's', '2025', 'cerrado')")
    conn.commit()


def _insert(conn, **kw):
    cols = list(kw.keys())
    sql = f"INSERT INTO matricula_academica ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    conn.execute(sql, [kw[c] for c in cols])
    conn.commit()


# ── Restricciones (BD temporal) ────────────────────────────────────────────

def test_estructura_creada_por_v24(temp_db):
    cols = [r[1] for r in temp_db.execute('PRAGMA table_info(anio_lectivo)').fetchall()]
    assert 'estado' in cols
    cols_ma = [r[1] for r in temp_db.execute('PRAGMA table_info(matricula_academica)').fetchall()]
    assert cols_ma == EXPECTED_COLS
    assert 'jornada_id' not in cols_ma and 'sede_id' not in cols_ma
    fks = {r['table']: r['on_delete'] for r in temp_db.execute(
        'PRAGMA foreign_key_list(matricula_academica)').fetchall()}
    assert sorted(fks.keys()) == ['anio_lectivo', 'cursos', 'estudiantes']
    assert all(v == 'RESTRICT' for v in fks.values())
    idx = [r['name'] for r in temp_db.execute('PRAGMA index_list(matricula_academica)').fetchall()]
    assert all(i in idx for i in EXPECTED_IDX)
    assert all(i not in idx for i in FORBIDDEN_IDX)


def test_migrar_v24_idempotente(temp_db):
    n_idx = len([r for r in temp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='matricula_academica'").fetchall()])
    _migrar_v24(temp_db, 'test_f24')
    n_idx2 = len([r for r in temp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='matricula_academica'").fetchall()])
    assert n_idx == n_idx2 == len(EXPECTED_IDX)


def test_migrar_v24_idempotente_con_filas_existentes():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    _crear_prerequisitos(conn)
    _migrar_v24(conn, 'test_repetido')  # primera ejecución correcta
    conn.execute("INSERT INTO anio_lectivo (slug, nombre, vigente) VALUES ('x', '2026', 0)")
    conn.commit()
    antes = [dict(r) for r in conn.execute('SELECT * FROM anio_lectivo').fetchall()]
    _migrar_v24(conn, 'test_repetido')  # segunda ejecución correcta
    despues = [dict(r) for r in conn.execute('SELECT * FROM anio_lectivo').fetchall()]
    assert despues == antes
    assert len(antes) == 1
    assert conn.execute('SELECT COUNT(*) c FROM anio_lectivo').fetchone()['c'] == 1
    cols = [r[1] for r in conn.execute('PRAGMA table_info(anio_lectivo)').fetchall()]
    assert 'estado' in cols
    conn.close()


def test_migrar_v24_defensiva_con_filas_legacy():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    _crear_prerequisitos(conn)
    conn.execute("INSERT INTO anio_lectivo (slug, nombre, vigente) VALUES ('x', 'legacy', 1)")
    conn.commit()
    with pytest.raises(RuntimeError):
        _migrar_v24(conn, 'test_legacy')
    cols = [r[1] for r in conn.execute('PRAGMA table_info(anio_lectivo)').fetchall()]
    assert 'estado' not in cols
    conn.close()


def test_aspirante_sin_anio_valido(temp_db):
    _semilla(temp_db)
    _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='aspirante')
    assert temp_db.execute('SELECT COUNT(*) c FROM matricula_academica').fetchone()['c'] == 1


def test_aspirante_con_anio_invalido(temp_db):
    _semilla(temp_db)
    with pytest.raises(sqlite3.IntegrityError):
        _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='aspirante', anio_lectivo_id=1)


def test_activo_sin_anio_invalido(temp_db):
    _semilla(temp_db)
    with pytest.raises(sqlite3.IntegrityError):
        _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='activo')


def test_activo_con_anio_valido(temp_db):
    _semilla(temp_db)
    _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='activo', anio_lectivo_id=1)
    assert temp_db.execute('SELECT COUNT(*) c FROM matricula_academica').fetchone()['c'] == 1


def test_retirado_sin_motivo_invalido(temp_db):
    _semilla(temp_db)
    with pytest.raises(sqlite3.IntegrityError):
        _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='retirado', anio_lectivo_id=1, fecha_fin='2026-06-01')


def test_retirado_con_motivo_valido(temp_db):
    _semilla(temp_db)
    _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='retirado',
            anio_lectivo_id=1, fecha_fin='2026-06-01', motivo_retiro='transferencia')
    assert temp_db.execute('SELECT COUNT(*) c FROM matricula_academica').fetchone()['c'] == 1


def test_no_retirado_con_motivo_invalido(temp_db):
    _semilla(temp_db)
    with pytest.raises(sqlite3.IntegrityError):
        _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='activo',
                anio_lectivo_id=1, motivo_retiro='x')


def test_fecha_fin_anterior_a_inicio_invalido(temp_db):
    _semilla(temp_db)
    with pytest.raises(sqlite3.IntegrityError):
        _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='activo',
                anio_lectivo_id=1, fecha_inicio='2026-09-01', fecha_fin='2026-08-01')


def test_estudiante_inexistente_fk(temp_db):
    _semilla(temp_db)
    with pytest.raises(sqlite3.IntegrityError):
        _insert(temp_db, slug='s', estudiante_id=999, curso_id=1, estado='aspirante')


def test_curso_inexistente_fk(temp_db):
    _semilla(temp_db)
    with pytest.raises(sqlite3.IntegrityError):
        _insert(temp_db, slug='s', estudiante_id=1, curso_id=999, estado='aspirante')


def test_anio_inexistente_fk(temp_db):
    _semilla(temp_db)
    with pytest.raises(sqlite3.IntegrityError):
        _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='activo', anio_lectivo_id=999)


def test_dos_activas_mismo_estudiante_anio_rechazado(temp_db):
    _semilla(temp_db)
    _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='activo', anio_lectivo_id=1)
    with pytest.raises(sqlite3.IntegrityError):
        _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='activo', anio_lectivo_id=1)


def test_dos_activas_mismo_estudiante_anios_distintos_permitido(temp_db):
    _semilla(temp_db)
    _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='activo', anio_lectivo_id=1)
    _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='activo', anio_lectivo_id=2)
    assert temp_db.execute('SELECT COUNT(*) c FROM matricula_academica').fetchone()['c'] == 2


def test_dos_aspirantes_mismo_estudiante_rechazado(temp_db):
    _semilla(temp_db)
    _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='aspirante')
    with pytest.raises(sqlite3.IntegrityError):
        _insert(temp_db, slug='s', estudiante_id=1, curso_id=2, estado='aspirante')


def test_aspirantes_estudiantes_distintos_permitido(temp_db):
    _semilla(temp_db)
    _insert(temp_db, slug='s', estudiante_id=1, curso_id=1, estado='aspirante')
    _insert(temp_db, slug='s', estudiante_id=2, curso_id=1, estado='aspirante')
    assert temp_db.execute('SELECT COUNT(*) c FROM matricula_academica').fetchone()['c'] == 2


# ── Estructura en BD reales (solo lectura) ────────────────────────────────

@pytest.mark.parametrize('slug', SLUGS_REALES)
def test_estructura_real_validacion_AL(slug):
    conn = sqlite3.connect(db_path(slug), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        anio_cols = [r[1] for r in conn.execute('PRAGMA table_info(anio_lectivo)').fetchall()]
        assert 'estado' in anio_cols  # A
        assert bool(conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='matricula_academica'").fetchone())  # C
        ma_cols = [r[1] for r in conn.execute('PRAGMA table_info(matricula_academica)').fetchall()]
        assert ma_cols == EXPECTED_COLS  # D
        assert 'jornada_id' not in ma_cols and 'sede_id' not in ma_cols  # E
        fks = {r['table']: r['on_delete'] for r in conn.execute(
            'PRAGMA foreign_key_list(matricula_academica)').fetchall()}
        assert sorted(fks.keys()) == ['anio_lectivo', 'cursos', 'estudiantes']  # F
        assert all(v == 'RESTRICT' for v in fks.values())  # G
        idx = [r['name'] for r in conn.execute('PRAGMA index_list(matricula_academica)').fetchall()]
        assert all(i in idx for i in EXPECTED_IDX)  # H
        assert all(i not in idx for i in FORBIDDEN_IDX)  # I, J
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []  # K
        assert conn.execute('SELECT COUNT(*) c FROM matricula_academica').fetchone()['c'] == 0  # L
        assert conn.execute('SELECT COUNT(*) c FROM anio_lectivo').fetchone()['c'] == 0
    finally:
        conn.close()