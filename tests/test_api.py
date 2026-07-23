import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'
import pytest

from flask_app import app, hash_pw, init_db

TEST_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'colegios_db', 'testcolegio.db')

def seed_api_test():
    init_db('testcolegio')
    import sqlite3
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("DELETE FROM rectores WHERE usuario='api_rector'")
    conn.execute("INSERT INTO rectores (id, nombre, usuario, password, email, activo, es_principal) VALUES (?,?,?,?,?,?,?)",
                 (199, 'API Rector', 'api_rector', hash_pw('test123'), 'api@test.com', 1, 1))
    conn.execute("DELETE FROM profesores WHERE usuario='api_prof'")
    conn.execute("INSERT INTO profesores (id, nombre, usuario, password, email, activo) VALUES (?,?,?,?,?,?)",
                 (199, 'API Prof', 'api_prof', hash_pw('test123'), 'api.prof@test.com', 1))
    cur = conn.execute("SELECT id FROM alumnos WHERE id=199")
    if not cur.fetchone():
        conn.execute("INSERT INTO alumnos (id, nombre, curso, jornada, activo) VALUES (?,?,?,?,?)",
                     (199, 'API Alumno', 'Primero A', 'Mañana', 1))
    conn.commit()
    conn.close()

seed_api_test()

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

def test_api_health(client):
    resp = client.get('/api/v1/health')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'ok'

def test_api_openapi_spec(client):
    resp = client.get('/api/v1/espec')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['openapi'] == '3.0.3'
    assert 'paths' in data

def test_api_login_missing_fields(client):
    resp = client.post('/api/v1/auth/login',
        content_type='application/json',
        data=json.dumps({}))
    assert resp.status_code == 400
    data = resp.get_json()
    assert 'MISSING_FIELDS' in data.get('code', '')

def _login_rector(client):
    resp = client.post('/api/v1/auth/login',
        content_type='application/json',
        data=json.dumps({'usuario': 'api_rector', 'password': 'test123', 'slug': 'testcolegio'}))
    data = resp.get_json()
    return data.get('token', '')

def test_api_login_rector(client):
    resp = client.post('/api/v1/auth/login',
        content_type='application/json',
        data=json.dumps({'usuario': 'api_rector', 'password': 'test123', 'slug': 'testcolegio'}))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['rol'] == 'rector'
    assert 'token' in data
    assert 'refresh_token' in data

def test_api_login_teacher(client):
    resp = client.post('/api/v1/auth/login',
        content_type='application/json',
        data=json.dumps({'usuario': 'api_prof', 'password': 'test123', 'slug': 'testcolegio'}))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['rol'] == 'teacher'

def test_api_login_wrong_password(client):
    resp = client.post('/api/v1/auth/login',
        content_type='application/json',
        data=json.dumps({'usuario': 'api_rector', 'password': 'wrong', 'slug': 'testcolegio'}))
    assert resp.status_code == 401

def test_api_login_invalid_slug(client):
    # conectar() creates empty DB without tables, expect 404
    resp = client.post('/api/v1/auth/login',
        content_type='application/json',
        data=json.dumps({'usuario': 'api_rector', 'password': 'test123', 'slug': 'nonesiste'}))
    assert resp.status_code == 404

def test_api_auth_me(client):
    token = _login_rector(client)
    if not token:
        pytest.skip('No se pudo obtener token')
    resp = client.get('/api/v1/auth/me',
        headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['rol'] == 'rector'

def test_api_auth_me_no_token(client):
    resp = client.get('/api/v1/auth/me')
    assert resp.status_code == 401

def test_api_students(client):
    token = _login_rector(client)
    if not token:
        pytest.skip('No se pudo obtener token')
    resp = client.get('/api/v1/students?slug=testcolegio',
        headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'data' in data

def test_api_student_detail(client):
    token = _login_rector(client)
    if not token:
        pytest.skip('No se pudo obtener token')
    resp = client.get('/api/v1/students/199?slug=testcolegio',
        headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['id'] == 199

def test_api_student_detail_not_found(client):
    token = _login_rector(client)
    if not token:
        pytest.skip('No se pudo obtener token')
    resp = client.get('/api/v1/students/9999?slug=testcolegio',
        headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 404

def test_api_courses(client):
    token = _login_rector(client)
    if not token:
        pytest.skip('No se pudo obtener token')
    resp = client.get('/api/v1/courses?slug=testcolegio',
        headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'data' in data

def test_api_teachers(client):
    token = _login_rector(client)
    if not token:
        pytest.skip('No se pudo obtener token')
    resp = client.get('/api/v1/teachers?slug=testcolegio',
        headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'data' in data

def test_api_teachers_no_auth(client):
    resp = client.get('/api/v1/teachers')
    assert resp.status_code in (401, 404)

def test_api_refresh(client):
    resp = client.post('/api/v1/auth/login',
        content_type='application/json',
        data=json.dumps({'usuario': 'api_rector', 'password': 'test123', 'slug': 'testcolegio'}))
    data = resp.get_json()
    refresh = data.get('refresh_token', '')
    if not refresh:
        pytest.skip('No se pudo obtener refresh token')
    resp2 = client.post('/api/v1/auth/refresh',
        content_type='application/json',
        data=json.dumps({'refresh_token': refresh}))
    assert resp2.status_code == 200
    assert 'token' in resp2.get_json()

def test_api_refresh_invalid(client):
    resp = client.post('/api/v1/auth/refresh',
        content_type='application/json',
        data=json.dumps({'refresh_token': 'invalid-token'}))
    assert resp.status_code == 401

def test_api_students_pagination(client):
    token = _login_rector(client)
    if not token:
        pytest.skip('No se pudo obtener token')
    resp = client.get('/api/v1/students?slug=testcolegio&page=1&per_page=10',
        headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['page'] == 1
    assert data['per_page'] == 10

def test_api_attendance_missing_params(client):
    token = _login_rector(client)
    if not token:
        pytest.skip('No se pudo obtener token')
    resp = client.get('/api/v1/attendance?slug=testcolegio',
        headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 400

def test_api_grades_missing_params(client):
    token = _login_rector(client)
    if not token:
        pytest.skip('No se pudo obtener token')
    resp = client.get('/api/v1/grades?slug=testcolegio',
        headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 400
