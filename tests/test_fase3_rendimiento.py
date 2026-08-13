"""FASE 3 — Rendimiento al guardar notas.

Valida el flujo optimizado de guardado de notas:
  - POST /<slug>/notas/batch devuelve `calculos` (promedio/nota_final por
    alumno) para que el front no haga N peticiones /recalcular.
  - El batch escribe todas las notas + auditoría en una sola conexión y un
    único commit (regresión: antes se abrían ~2 conexiones por nota).
  - El guardado individual /guardar_nota sigue funcionando y audita.

Usa actividades/alumnos del seed (actividad id 1, alumnos id 1 y 2) para
evitar la ruta lenta /actividades/crear y centrarse en el contrato del batch.
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
CSRF = 'fase3_rendimiento_csrf'
ACT_ID = 1  # 'Tarea 1' — Primero A, Matematicas, Manana, periodo 1, profesor_id 1
AID = 1     # 'Alumno Uno'
AID2 = 2    # 'Alumno Dos'


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


def db():
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    return conn


def asegurar_periodo_abierto():
    conn = db()
    conn.execute('INSERT OR REPLACE INTO periodos_estado (periodo, estado) VALUES (?, ?)', (1, 'abierto'))
    conn.commit()
    conn.close()


def test_notas_batch_devuelve_calculos(teacher):
    asegurar_periodo_abierto()
    r = teacher.post(f'/{SLUG}/notas/batch', json={'notas': [
        {'aid': AID, 'actividad_id': ACT_ID, 'val': 4.0},
        {'aid': AID2, 'actividad_id': ACT_ID, 'val': 3.5},
    ]}, headers={'X-CSRF-Token': CSRF})
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data['status'] == 'ok'
    assert 'calculos' in data
    assert str(AID) in data['calculos'] and str(AID2) in data['calculos']
    calc = data['calculos'][str(AID)]
    assert 'promedio' in calc and 'nota_final' in calc


def test_notas_batch_escribe_y_audita(teacher):
    asegurar_periodo_abierto()
    r = teacher.post(f'/{SLUG}/notas/batch', json={'notas': [
        {'aid': AID, 'actividad_id': ACT_ID, 'val': 3.6},
    ]}, headers={'X-CSRF-Token': CSRF})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['status'] == 'ok'
    conn = db()
    fila = conn.execute('SELECT val FROM notas WHERE aid=? AND actividad_id=?', (AID, ACT_ID)).fetchone()
    assert fila is not None and float(fila['val']) == 3.6
    aud = conn.execute("SELECT COUNT(*) as c FROM auditoria_notas WHERE aid=? AND actividad_id=?",
                       (AID, ACT_ID)).fetchone()
    conn.close()
    assert aud['c'] >= 1


def test_notas_batch_sin_datos(teacher):
    r = teacher.post(f'/{SLUG}/notas/batch', json={'notas': []}, headers={'X-CSRF-Token': CSRF})
    assert r.status_code == 400


def test_notas_batch_requiere_csrf(teacher):
    r = teacher.post(f'/{SLUG}/notas/batch', json={'notas': [
        {'aid': AID, 'actividad_id': ACT_ID, 'val': 4.0}]})
    assert r.status_code in (400, 403)


def test_guardar_nota_individual_sigue_funcionando(teacher):
    asegurar_periodo_abierto()
    r = teacher.post(f'/{SLUG}/guardar_nota', data={
        'actividad_id': ACT_ID, 'aid': AID, 'val': '4.5', '_csrf_token': CSRF})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['status'] == 'ok'
    conn = db()
    fila = conn.execute('SELECT val FROM notas WHERE aid=? AND actividad_id=?', (AID, ACT_ID)).fetchone()
    conn.close()
    assert fila is not None and float(fila['val']) == 4.5


def test_notas_batch_borrar_nota(teacher):
    asegurar_periodo_abierto()
    r = teacher.post(f'/{SLUG}/notas/batch', json={'notas': [
        {'aid': AID, 'actividad_id': ACT_ID, 'val': None},
    ]}, headers={'X-CSRF-Token': CSRF})
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data['status'] == 'ok'
    assert data['errors'] == []
    conn = db()
    fila = conn.execute('SELECT val FROM notas WHERE aid=? AND actividad_id=?', (AID, ACT_ID)).fetchone()
    conn.close()
    assert fila is None


def test_notas_batch_periodo_cerrado(teacher):
    conn = db()
    conn.execute('INSERT OR REPLACE INTO periodos_estado (periodo, estado) VALUES (?, ?)', (1, 'cerrado'))
    conn.commit()
    conn.close()
    r = teacher.post(f'/{SLUG}/notas/batch', json={'notas': [
        {'aid': AID, 'actividad_id': ACT_ID, 'val': 4.0},
    ]}, headers={'X-CSRF-Token': CSRF})
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data['status'] == 'ok'
    assert any(e.get('error') == 'Periodo cerrado' for e in data['errors'])
    assert data['saved'] == 0


def test_notas_batch_valor_invalido(teacher):
    asegurar_periodo_abierto()
    r = teacher.post(f'/{SLUG}/notas/batch', json={'notas': [
        {'aid': AID, 'actividad_id': ACT_ID, 'val': 'abc'},
        {'aid': AID, 'actividad_id': ACT_ID, 'val': True},
        {'aid': AID, 'actividad_id': ACT_ID, 'val': 15.0},
    ]}, headers={'X-CSRF-Token': CSRF})
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data['status'] == 'ok'
    assert len(data['errors']) == 3
    assert all(e.get('error') != 'Datos invalidos' for e in data['errors'])
    assert data['saved'] == 0


def test_notas_batch_rechaza_nan(teacher):
    """NaN (de JSON 'NaN') no debe persistirse: se rechaza como valor invalido."""
    import json
    asegurar_periodo_abierto()
    payload = json.dumps({'notas': [{'aid': AID, 'actividad_id': ACT_ID, 'val': float('nan')}]})
    r = teacher.post(f'/{SLUG}/notas/batch', data=payload, content_type='application/json',
                     headers={'X-CSRF-Token': CSRF})
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data['status'] == 'ok'
    assert data['saved'] == 0
    assert any(e.get('error') == 'Valor invalido' for e in data['errors'])
    conn = db()
    fila = conn.execute('SELECT val FROM notas WHERE aid=? AND actividad_id=?', (AID, ACT_ID)).fetchone()
    conn.close()
    assert fila is None or not (fila['val'] != fila['val'])


def test_notas_deshacer_restaura_tras_borrado(teacher):
    """Deshacer un borrado en batch debe re-crear la fila (upsert), no fallar."""
    asegurar_periodo_abierto()
    r = teacher.post(f'/{SLUG}/notas/batch', json={'notas': [
        {'aid': AID, 'actividad_id': ACT_ID, 'val': 4.0}]}, headers={'X-CSRF-Token': CSRF})
    assert r.get_json()['status'] == 'ok'
    r = teacher.post(f'/{SLUG}/notas/batch', json={'notas': [
        {'aid': AID, 'actividad_id': ACT_ID, 'val': None}]}, headers={'X-CSRF-Token': CSRF})
    assert r.get_json()['status'] == 'ok'
    conn = db()
    fila = conn.execute('SELECT val FROM notas WHERE aid=? AND actividad_id=?', (AID, ACT_ID)).fetchone()
    conn.close()
    assert fila is None
    r = teacher.post(f'/{SLUG}/notas/deshacer', json={'aid': AID, 'actividad_id': ACT_ID, 'val': 4.0},
                     headers={'X-CSRF-Token': CSRF})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['status'] == 'ok'
    conn = db()
    fila = conn.execute('SELECT val FROM notas WHERE aid=? AND actividad_id=?', (AID, ACT_ID)).fetchone()
    conn.close()
    assert fila is not None and float(fila['val']) == 4.0


def test_notas_deshacer_elimina_creacion(teacher):
    """Deshacer una creación (val_anterior None) debe borrar la nota."""
    asegurar_periodo_abierto()
    r = teacher.post(f'/{SLUG}/notas/batch', json={'notas': [
        {'aid': AID, 'actividad_id': ACT_ID, 'val': 3.2}]}, headers={'X-CSRF-Token': CSRF})
    assert r.get_json()['status'] == 'ok'
    r = teacher.post(f'/{SLUG}/notas/deshacer', json={'aid': AID, 'actividad_id': ACT_ID, 'val': None},
                     headers={'X-CSRF-Token': CSRF})
    assert r.status_code == 200, r.get_data(as_text=True)
    conn = db()
    fila = conn.execute('SELECT val FROM notas WHERE aid=? AND actividad_id=?', (AID, ACT_ID)).fetchone()
    conn.close()
    assert fila is None
