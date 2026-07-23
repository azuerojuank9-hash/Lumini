import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'
import pytest

from flask_app import app, init_db

TEST_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'colegios_db', 'testcolegio.db')

def seed():
    init_db('testcolegio')
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("DELETE FROM rectores WHERE usuario='rector_prueba'")
    conn.execute("INSERT INTO rectores (id, nombre, usuario, password, email, activo, es_principal) VALUES (?,?,?,?,?,?,?)",
                 (99, 'Rector Prueba', 'rector_prueba', 'fake', 'rector@test.com', 1, 1))
    conn.commit()
    conn.close()

seed()

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

@pytest.fixture
def rector_session(client):
    with client.session_transaction() as sess:
        sess['logueado'] = True
        sess['usuario'] = 'rector_prueba'
        sess['nombre'] = 'Rector Prueba'
        sess['rol'] = 'rector'
        sess['slug'] = 'testcolegio'
        sess['_csrf_token'] = 'pytest_csrf'
        sess['rector_id_testcolegio'] = 99

def test_expediente_page_loads(client, rector_session):
    resp = client.get('/testcolegio/rector/expediente')
    assert resp.status_code == 200
    html = resp.data.decode()
    assert 'expediente' in html.lower() or 'Expediente' in html or 'Observador' in html

def test_expediente_with_student(client, rector_session):
    resp = client.get('/testcolegio/rector/expediente?aid=1')
    assert resp.status_code == 200

def test_expediente_with_invalid_student(client, rector_session):
    resp = client.get('/testcolegio/rector/expediente?aid=99999')
    assert resp.status_code == 200

def test_observador_page_loads(client, rector_session):
    resp = client.get('/testcolegio/rector/observador')
    assert resp.status_code == 200
    html = resp.data.decode()
    assert 'Observador' in html or 'observador' in html

def test_certificados_page_loads(client, rector_session):
    resp = client.get('/testcolegio/rector/certificados')
    assert resp.status_code == 200

def test_calendario_page_loads(client, rector_session):
    resp = client.get('/testcolegio/rector/calendario')
    assert resp.status_code == 200

def test_mensajes_page_loads(client, rector_session):
    resp = client.get('/testcolegio/rector/mensajes')
    assert resp.status_code == 200

def test_api_rector_estudiantes_search(client, rector_session):
    resp = client.get('/testcolegio/api/rector/estudiantes?q=Alumno')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert len(data['data']) > 0

def test_api_rector_estudiantes_short_query(client, rector_session):
    resp = client.get('/testcolegio/api/rector/estudiantes?q=A')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is False

def test_api_rector_observador_get(client, rector_session):
    resp = client.get('/testcolegio/api/rector/observador/1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'data' in data

def test_api_rector_observador_post(client, rector_session):
    resp = client.post('/testcolegio/api/rector/observador/1',
        content_type='application/json',
        data=json.dumps({'tipo': 'llamado', 'texto': 'Llamado de atencion por comportamiento'}),
        headers={'X-CSRF-Token': 'pytest_csrf'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True

def test_api_rector_observador_post_no_text(client, rector_session):
    resp = client.post('/testcolegio/api/rector/observador/1',
        content_type='application/json',
        data=json.dumps({'tipo': 'llamado', 'texto': ''}),
        headers={'X-CSRF-Token': 'pytest_csrf'})
    assert resp.status_code == 400

def test_api_rector_observador_post_no_csrf(client, rector_session):
    resp = client.post('/testcolegio/api/rector/observador/1',
        content_type='application/json',
        data=json.dumps({'tipo': 'llamado', 'texto': 'test'}))
    assert resp.status_code == 400

def test_expediente_no_mojibake(client, rector_session):
    resp = client.get('/testcolegio/rector/expediente?aid=1')
    html = resp.data.decode('utf-8')
    for bad in ['\ufffd', 'Ã¡', 'Ã©', 'Ã\xad', 'Ã³', 'Ãº']:
        assert bad not in html

def test_observador_no_mojibake(client, rector_session):
    resp = client.get('/testcolegio/rector/observador')
    html = resp.data.decode('utf-8')
    for bad in ['\ufffd', 'Ã¡', 'Ã©', 'Ã\xad', 'Ã³', 'Ãº']:
        assert bad not in html
