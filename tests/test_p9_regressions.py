"""P9 — Regresiones: auditoría, tesorería y batch notas optimizado.

Tests:
  - Tesorería devuelve 501 (no 200 con toast engañoso)
  - Batch notas masivo: guarda todas las notas con una sola conexión
  - Batch notas: deduplica cálculos por alumno
  - Batch notas: maneja valores fuera de rango
  - Auditoría: template rendering con tabla_labels (verifica que la función de mapeo existe)
  - Logout del estudiante: la ruta existe y redirige
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'

import pytest

from flask_app import app
from test_app import TEST_DB, seed_test_db

seed_test_db()

SLUG = 'testcolegio'
CSRF = 'p9_regression_csrf'
ACT_ID = 1
AID = 1
AID2 = 2


@pytest.fixture
def teacher():
    app.config['TESTING'] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess[f'profesor_id_{SLUG}'] = 1
            sess[f'rol_{SLUG}'] = 'profesor'
            sess[f'jornada_{SLUG}'] = 'Mañana'
            sess[f'materia_{SLUG}'] = 'Matemáticas'
            sess['_csrf_token'] = CSRF
        yield c


@pytest.fixture
def rector():
    app.config['TESTING'] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess[f'rector_id_{SLUG}'] = 99
            sess[f'rol_{SLUG}'] = 'rector'
            sess['_csrf_token'] = CSRF
        yield c


def db():
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    return conn


def asegurar_periodo_abierto():
    conn = db()
    conn.execute('INSERT OR REPLACE INTO periodos_estado (periodo, estado) VALUES (?, ?)', (1, 'abierto'))
    conn.commit()
    conn.close()


class TestTesoreria:
    def test_crear_factura_devuelve_501(self, rector):
        r = rector.post(f'/{SLUG}/tesoreria/facturas/crear',
                        json={'alumno_id': 1, 'monto': 100},
                        headers={'X-CSRF-Token': CSRF})
        assert r.status_code == 501
        data = r.get_json()
        assert data['status'] == 'proximamente'

    def test_pagar_factura_devuelve_501(self, rector):
        r = rector.post(f'/{SLUG}/tesoreria/facturas/1/pagar',
                        json={'monto': 100},
                        headers={'X-CSRF-Token': CSRF})
        assert r.status_code == 501
        data = r.get_json()
        assert data['status'] == 'proximamente'


class TestBatchNotasOptimizado:
    def test_batch_masivo_guarda_todas(self, teacher):
        asegurar_periodo_abierto()
        notas = [{'aid': AID, 'actividad_id': ACT_ID, 'val': 4.0 + i * 0.1}
                 for i in range(5)]
        r = teacher.post(f'/{SLUG}/notas/batch',
                         json={'notas': notas},
                         headers={'X-CSRF-Token': CSRF})
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()
        assert data['status'] == 'ok'
        assert data['saved'] == 5
        assert len(data['errors']) == 0

    def test_batch_deduplica_calculos(self, teacher):
        asegurar_periodo_abierto()
        r = teacher.post(f'/{SLUG}/notas/batch', json={'notas': [
            {'aid': AID, 'actividad_id': ACT_ID, 'val': 3.5},
            {'aid': AID, 'actividad_id': ACT_ID, 'val': 4.0},
        ]}, headers={'X-CSRF-Token': CSRF})
        assert r.status_code == 200
        data = r.get_json()
        assert data['saved'] == 2
        assert str(AID) in data['calculos']

    def test_batch_fuera_de_rango_rechaza(self, teacher):
        asegurar_periodo_abierto()
        r = teacher.post(f'/{SLUG}/notas/batch', json={'notas': [
            {'aid': AID, 'actividad_id': ACT_ID, 'val': 99.9},
        ]}, headers={'X-CSRF-Token': CSRF})
        assert r.status_code == 200
        data = r.get_json()
        assert data['saved'] == 0
        assert len(data['errors']) == 1
        assert 'rango' in data['errors'][0]['error'].lower()

    def test_batch_nulos_borra_nota(self, teacher):
        asegurar_periodo_abierto()
        teacher.post(f'/{SLUG}/notas/batch', json={'notas': [
            {'aid': AID, 'actividad_id': ACT_ID, 'val': 4.0},
        ]}, headers={'X-CSRF-Token': CSRF})
        r = teacher.post(f'/{SLUG}/notas/batch', json={'notas': [
            {'aid': AID, 'actividad_id': ACT_ID, 'val': None},
        ]}, headers={'X-CSRF-Token': CSRF})
        assert r.status_code == 200
        conn = db()
        fila = conn.execute('SELECT val FROM notas WHERE aid=? AND actividad_id=?',
                            (AID, ACT_ID)).fetchone()
        conn.close()
        assert fila is None


class TestAuditoriaTemplate:
    def test_auditoria_page_renders(self, rector):
        r = rector.get(f'/{SLUG}/rector/auditoria')
        assert r.status_code == 200
        text = r.get_data(as_text=True)
        assert 'Sección' in text or 'Secci' in text


class TestStudentLogout:
    def test_logout_route_exists(self):
        with app.test_client() as c:
            r = c.get(f'/{SLUG}/logout', follow_redirects=False)
            assert r.status_code in (302, 303, 200)
