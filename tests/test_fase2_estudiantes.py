"""FASE 2 — Gestión de estudiantes (rector).

Cubre el flujo corregido: alta de estudiante (POST /matriculas/crear con
nombre/curso/jornada), edición (POST /matriculas/<id>/editar), activación/
desactivación (POST /matriculas/<id>/estado) y la página rector/estudiantes
con su UI de gestión (Agregar / Editar / Activar / Desactivar).

Regresiones clave:
  - La UI de "Matrículas" ya envía los campos que el backend espera.
  - rector_estudiantes muestra también estudiantes inactivos (badge).
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
CSRF = 'fase2_estudiantes_csrf'


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess[f'rector_id_{SLUG}'] = 99
            sess['_csrf_token'] = CSRF
        yield c


def db():
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    return conn


def crear_estudiante(client, nombre='F2 Alumno', curso='5A', jornada='Mañana'):
    return client.post(f'/{SLUG}/matriculas/crear', json={
        'nombre': nombre, 'curso': curso, 'jornada': jornada,
    }, headers={'X-CSRF-Token': CSRF})


def test_rector_estudiantes_page_muestra_ui_gestion(client):
    r = client.get(f'/{SLUG}/rector/estudiantes')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Agregar estudiante' in html
    assert 'abrirModalEstudiante' in html
    assert 'Editar' in html
    assert 'Activo' in html


def test_matriculas_crear_ok(client):
    r = crear_estudiante(client, 'F2 Alta', '7B', 'Tarde')
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['status'] == 'ok'
    conn = db()
    fila = conn.execute("SELECT id, nombre, curso, jornada, activo FROM alumnos WHERE nombre='F2 Alta'").fetchone()
    conn.close()
    assert fila is not None
    assert fila['curso'] == '7B'
    assert fila['jornada'] == 'Tarde'
    assert fila['activo'] == 1


def test_matriculas_crear_validacion(client):
    r = client.post(f'/{SLUG}/matriculas/crear', json={'nombre': 'Sin Curso'},
                    headers={'X-CSRF-Token': CSRF})
    assert r.status_code == 400


def test_matriculas_editar(client):
    crear_estudiante(client, 'F2 Editar', '3A', 'Mañana')
    conn = db()
    fila = conn.execute("SELECT id FROM alumnos WHERE nombre='F2 Editar'").fetchone()
    conn.close()
    assert fila is not None
    r = client.post(f'/{SLUG}/matriculas/{fila["id"]}/editar', json={
        'nombre': 'F2 Editado', 'curso': '9C', 'jornada': 'Nocturna',
    }, headers={'X-CSRF-Token': CSRF})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['status'] == 'ok'
    conn = db()
    fila2 = conn.execute('SELECT nombre, curso, jornada FROM alumnos WHERE id=?', (fila['id'],)).fetchone()
    conn.close()
    assert fila2['nombre'] == 'F2 Editado'
    assert fila2['curso'] == '9C'
    assert fila2['jornada'] == 'Nocturna'


def test_matriculas_editar_validacion(client):
    crear_estudiante(client, 'F2 Editar Val')
    conn = db()
    fila = conn.execute("SELECT id FROM alumnos WHERE nombre='F2 Editar Val'").fetchone()
    conn.close()
    r = client.post(f'/{SLUG}/matriculas/{fila["id"]}/editar', json={'nombre': 'X'},
                    headers={'X-CSRF-Token': CSRF})
    assert r.status_code == 400


def test_matriculas_estado_desactiva(client):
    crear_estudiante(client, 'F2 Desactivar')
    conn = db()
    fila = conn.execute("SELECT id FROM alumnos WHERE nombre='F2 Desactivar'").fetchone()
    conn.close()
    r = client.post(f'/{SLUG}/matriculas/{fila["id"]}/estado', json={'estado': 'rechazado'},
                    headers={'X-CSRF-Token': CSRF})
    assert r.status_code == 200
    conn = db()
    act = conn.execute('SELECT activo FROM alumnos WHERE id=?', (fila['id'],)).fetchone()
    conn.close()
    assert act['activo'] == 0


def test_editar_requiere_csrf(client):
    crear_estudiante(client, 'F2 CSRF')
    conn = db()
    fila = conn.execute("SELECT id FROM alumnos WHERE nombre='F2 CSRF'").fetchone()
    conn.close()
    r = client.post(f'/{SLUG}/matriculas/{fila["id"]}/editar', json={
        'nombre': 'F2 No', 'curso': '1A', 'jornada': 'Mañana'})
    assert r.status_code == 400


def test_editar_requiere_rector(client):
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['_csrf_token'] = CSRF
        r = c.post(f'/{SLUG}/matriculas/1/editar', json={
            'nombre': 'F2 SinPermiso', 'curso': '1A', 'jornada': 'Mañana'},
            headers={'X-CSRF-Token': CSRF})
        assert r.status_code == 403
