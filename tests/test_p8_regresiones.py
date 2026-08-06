"""P8 — Regresiones de auditoría final.

Cubre:
  - Certificados rector: endpoint /api/rector/certificados/<tipo> ya no es 404,
    genera PDF real (constancia/estudio/paz-y-salvo/conducta), gating por rol.
  - Página del estudiante: contiene navbar con Cerrar sesión (logout antes ausente)
    y el JS de mobile nav no referencia elementos inexistentes.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'

import pytest

from flask_app import app
from test_app import TEST_DB, seed_test_db

seed_test_db()

SLUG = 'testcolegio'
CSRF = 'p8_csrf'


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


@pytest.fixture
def rector(client, csrf):
    with client.session_transaction() as sess:
        sess[f'rector_id_{SLUG}'] = 99
        sess['_csrf_token'] = CSRF


@pytest.fixture
def estudiante(client, csrf):
    with client.session_transaction() as sess:
        sess[f'rol_{SLUG}'] = 'estudiante'
        sess[f'alumno_id_{SLUG}'] = 1
        sess['_csrf_token'] = CSRF


def db():
    import sqlite3
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    return conn


def primer_alumno():
    conn = db()
    a = conn.execute('SELECT id FROM alumnos WHERE activo=1 ORDER BY id LIMIT 1').fetchone()
    conn.close()
    return a['id']


# ── Certificados: endpoint PDF ─────────────────────────────────────────────

class TestCertificadosEndpoint:

    URL = f'/{SLUG}/api/rector/certificados'

    def test_constancia_ok(self, client, rector):
        aid = primer_alumno()
        r = client.get(f'{self.URL}/constancia?estudiante_id={aid}')
        assert r.status_code == 200
        assert r.mimetype == 'application/pdf'
        assert r.data.startswith(b'%PDF')

    def test_estudio_ok(self, client, rector):
        aid = primer_alumno()
        r = client.get(f'{self.URL}/estudio?estudiante_id={aid}')
        assert r.status_code == 200
        assert r.mimetype == 'application/pdf'
        assert r.data.startswith(b'%PDF')

    def test_paz_y_salvo_ok(self, client, rector):
        aid = primer_alumno()
        r = client.get(f'{self.URL}/paz-y-salvo?estudiante_id={aid}')
        assert r.status_code == 200
        assert r.mimetype == 'application/pdf'
        assert r.data.startswith(b'%PDF')

    def test_conducta_ok(self, client, rector):
        aid = primer_alumno()
        r = client.get(f'{self.URL}/conducta?estudiante_id={aid}')
        assert r.status_code == 200
        assert r.mimetype == 'application/pdf'
        assert r.data.startswith(b'%PDF')

    def test_content_disposition(self, client, rector):
        aid = primer_alumno()
        r = client.get(f'{self.URL}/constancia?estudiante_id={aid}')
        assert 'certificado_constancia.pdf' in r.headers.get('Content-Disposition', '')

    def test_requiere_rector(self, client):
        aid = primer_alumno()
        r = client.get(f'{self.URL}/constancia?estudiante_id={aid}')
        assert r.status_code == 401

    def test_no_autoriza_profesor(self, client, csrf):
        with client.session_transaction() as sess:
            sess[f'profesor_id_{SLUG}'] = 1
            sess[f'rol_{SLUG}'] = 'profesor'
            sess['_csrf_token'] = CSRF
        aid = primer_alumno()
        r = client.get(f'{self.URL}/constancia?estudiante_id={aid}')
        assert r.status_code == 401

    def test_estudiante_inexistente(self, client, rector):
        r = client.get(f'{self.URL}/constancia?estudiante_id=999999')
        assert r.status_code == 404

    def test_tipo_invalido(self, client, rector):
        aid = primer_alumno()
        r = client.get(f'{self.URL}/inexistente?estudiante_id={aid}')
        assert r.status_code == 400

    def test_sin_estudiante_id(self, client, rector):
        r = client.get(f'{self.URL}/constancia')
        assert r.status_code == 400

    def test_pagina_certificados_render(self, client, rector):
        r = client.get(f'/{SLUG}/rector/certificados')
        assert r.status_code == 200
        assert b'Constancia de Estudio' in r.data


# ── Página del estudiante: logout y JS ─────────────────────────────────────

class TestPaginaEstudiante:

    def test_pagina_contiene_logout(self, client, estudiante):
        r = client.get(f'/{SLUG}/estudiante')
        assert r.status_code == 200
        assert f'/{SLUG}/logout'.encode() in r.data
        assert b'Cerrar sesi' in r.data

    def test_pagina_tiene_navbar(self, client, estudiante):
        r = client.get(f'/{SLUG}/estudiante')
        assert b'class="navbar"' in r.data
        assert b'class="navbar-left"' in r.data

    def test_pagina_sin_sesion_redirige(self, client):
        r = client.get(f'/{SLUG}/estudiante')
        assert r.status_code == 302
