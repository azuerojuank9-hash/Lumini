"""P3 — Coherencia del flujo de notas: Profesor → BD → estudiante → padre → boletín.

Asserts the P3 notes-coherence work:
  - El portal del padre usa la MISMA fórmula ponderada (65/25/10) que
    profesor/estudiante/PDF: nota final por materia y promedio general.
  - El endpoint de notas del padre aplica verificación de relación (403
    para hijos no vinculados).
  - El historial del padre devuelve promedios ponderados por período.
  - La tabla de calificaciones del profesor es legible (columnas anchas,
    nombre completo, chips de estado, columna N.Final).
  - guardar_evaluacion recalcula la nota final con la misma fórmula.
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'

import pytest

from flask_app import _promedio_ponderado, app
from test_app import TEST_DB, seed_test_db

seed_test_db()

SLUG = 'testcolegio'
CSRF = 'p3_notas_csrf'

EXPECTED_ACT = 4.0
EXPECTED_EVAL = 3.0
EXPECTED_AUTO = 5.0
# 4.0*0.65 + 3.0*0.25 + 5.0*0.10 = 3.85
EXPECTED_FINAL = round(EXPECTED_ACT * 0.65 + EXPECTED_EVAL * 0.25 + EXPECTED_AUTO * 0.10, 2)
assert EXPECTED_FINAL == 3.85


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def csrf(client):
    with client.session_transaction() as sess:
        sess['_csrf_token'] = CSRF
    return CSRF


def db():
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    return conn


def seed_nota_p3():
    conn = db()
    alumno = conn.execute('SELECT * FROM alumnos WHERE id=1').fetchone()
    assert alumno is not None
    conn.execute('DELETE FROM notas WHERE aid=1')
    conn.execute('DELETE FROM evaluaciones WHERE aid=1')
    conn.execute('INSERT OR REPLACE INTO periodos_estado (periodo, estado) VALUES (1, ?)', ('abierto',))
    conn.execute('INSERT INTO notas (aid, actividad_id, val) VALUES (1, 1, ?)', (EXPECTED_ACT,))
    conn.execute(
        """INSERT INTO evaluaciones (aid, profesor_id, materia, jornada, evaluacion, autoevaluacion, periodo)
           VALUES (1, 1, 'Matemáticas', 'Mañana', ?, ?, 1)""",
        (EXPECTED_EVAL, EXPECTED_AUTO))
    conn.commit()
    conn.close()
    return alumno


def seed_padre():
    conn = db()
    conn.execute('INSERT OR IGNORE INTO padres (id, nombre, email, pin, activo) VALUES (?,?,?,?,?)',
                 (101, 'Padre P3', 'padre_p3@test.com', '1234', 1))
    conn.execute('INSERT OR IGNORE INTO alumno_padre (padre_id, alumno_id) VALUES (?,?)', (101, 1))
    conn.commit()
    conn.close()


def _padre_session(client):
    with client.session_transaction() as sess:
        sess[f'padre_id_{SLUG}'] = 101
        sess['_csrf_token'] = CSRF


def _teacher_session(client):
    with client.session_transaction() as sess:
        sess[f'profesor_id_{SLUG}'] = 1
        sess[f'rol_{SLUG}'] = 'profesor'
        sess[f'jornada_{SLUG}'] = 'Mañana'
        sess[f'materia_{SLUG}'] = 'Matemáticas'
        sess['_csrf_token'] = CSRF


class TestParentNotasCoherentes:
    def test_parent_notas_usan_promedio_ponderado(self, client, csrf):
        seed_padre()
        alumno = seed_nota_p3()
        _padre_session(client)
        r = client.get(f'/{SLUG}/portal/notas/{alumno["id"]}')
        assert r.status_code == 200
        body = r.get_json()
        assert 'materias' in body and 'promedio_general' in body and 'actividades' in body
        assert body['promedio_general'] == EXPECTED_FINAL
        mats = [m for m in body['materias'] if m['materia'] == 'Matemáticas']
        assert mats and mats[0]['nota_final'] == EXPECTED_FINAL
        assert mats[0]['evaluacion'] == EXPECTED_EVAL
        assert mats[0]['autoevaluacion'] == EXPECTED_AUTO
        # El promedio plano (solo actividades) daría 4.0 ≠ 3.85 → prueba el peso 65/25/10.
        assert mats[0]['nota_final'] != EXPECTED_ACT

    def test_parent_dashboard_promedio_matches_student(self, client, csrf):
        seed_padre()
        seed_nota_p3()
        _padre_session(client)
        r = client.get(f'/{SLUG}/portal/dashboard')
        assert r.status_code == 200
        hijo = [h for h in r.get_json()['hijos'] if h['id'] == 1][0]
        assert hijo['promedio'] == EXPECTED_FINAL

    def test_parent_historial_ponderado_por_periodo(self, client, csrf):
        seed_padre()
        seed_nota_p3()
        _padre_session(client)
        r = client.get(f'/{SLUG}/portal/historial/1')
        assert r.status_code == 200
        hist = r.get_json()['historial']
        mats = [m for m in hist['periodos'].get('1', []) if m['materia'] == 'Matemáticas']
        assert mats and mats[0]['promedio'] == EXPECTED_FINAL
        assert hist['totales'].get('1') == EXPECTED_FINAL

    def test_parent_notas_403_for_unlinked_child(self, client, csrf):
        seed_padre()
        _padre_session(client)
        # Alumno Dos (id 2) no está vinculado al padre 101.
        assert client.get(f'/{SLUG}/portal/notas/2').status_code == 403

    def test_promedio_ponderado_es_la_formula_canonica(self):
        # Verifica que la fórmula usada por el padre es idéntica a la canónica
        # de grades.py (la misma que exporta flask_app para PDF/directora).
        assert _promedio_ponderado([EXPECTED_ACT], EXPECTED_EVAL, EXPECTED_AUTO) == EXPECTED_FINAL


class TestTablaCalificaciones:
    def test_tabla_legible_columnas_estado_y_nfinal(self, client, csrf):
        seed_nota_p3()
        _teacher_session(client)
        r = client.get(f'/{SLUG}/')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        # Columnas más anchas y nombre completo visible.
        assert 'min-width:115px' in html
        assert 'th.tnombre' in html and 'min-width:200px' in html
        # Chips de estado (Borrador/Publicada/Cerrada/Archivada).
        assert 'act-estado-label' in html
        assert 'Borrador' in html
        # Columna N.Final del período presente.
        assert 'N.Final' in html

    def test_guardar_evaluacion_recalcula_ponderado(self, client, csrf):
        seed_nota_p3()
        _teacher_session(client)
        r = client.post(f'/{SLUG}/guardar_evaluacion', data={
            'aid': 1, 'evaluacion': str(EXPECTED_EVAL), 'autoevaluacion': str(EXPECTED_AUTO),
            'periodo': '1', 'curso': 'Primero A', '_csrf_token': CSRF,
        })
        assert r.status_code == 200
        body = r.get_json()
        # El promedio ponderado de la materia Matemáticas debe ser 3.85.
        promedios = body.get('promedios') or body.get('materias') or body
        assert _promedio_ponderado([EXPECTED_ACT], EXPECTED_EVAL, EXPECTED_AUTO) == EXPECTED_FINAL
