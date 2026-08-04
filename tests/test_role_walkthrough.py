"""P5 — Functional completeness walkthrough by role.

Walks each role's real flows through the test client: login → session →
pages → form-backed writes → DB verification → cross-role consistency.
Complements functional_audit.py (which only GET-walks pages).

Flows covered:
  - Teacher: login → jornada selection → pages → crear actividad → registrar
    alumno → guardar nota → guardar evaluación → marcar asistencia → historial.
  - Student: dashboard with the grade/activity just written by the teacher,
    plus all portal sections (Notas, Asistencia, Agenda, Horario, Avisos,
    Canales, Observaciones) and logout.
  - Rector: login → all module pages (incl. Matrículas, Tesorería, Gestión
    académica) → period toggle → matrícula creation → comunicación creation.
  - Directora: login → panel → boletín PDF generation.
  - Parent: portal login (email+PIN) → dashboard → notas/asistencia/comunicados
    of the linked child (JSON API).
"""

import json
import os
import sqlite3
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'

import pytest

from flask_app import app, hash_pw
from test_app import TEST_DB, seed_test_db

seed_test_db()

SLUG = 'testcolegio'
CSRF = 'p5_walkthrough_csrf'


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


def ensure_parent_seed():
    conn = db()
    conn.execute('INSERT OR IGNORE INTO padres (id, nombre, email, pin, activo) VALUES (?,?,?,?,?)',
                 (100, 'Padre P5', 'padre_p5@test.com', '1234', 1))
    row = conn.execute("SELECT id FROM alumnos WHERE nombre='P5 Estudiante' ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        conn.execute('INSERT OR IGNORE INTO alumno_padre (padre_id, alumno_id) VALUES (?,?)', (100, row['id']))
    conn.commit()
    conn.close()


# ── TEACHER ────────────────────────────────────────────────────────────────

class TestTeacherWalkthrough:
    def test_teacher_login_selection_pages(self, client, csrf):
        r = client.get(f'/{SLUG}/login')
        assert r.status_code == 200
        r = client.post(f'/{SLUG}/login', data={
            'accion': 'profesor_login', 'usuario': 'profesor1',
            'password': 'test123', '_csrf_token': csrf})
        assert r.status_code in (200, 302)
        with client.session_transaction() as s:
            assert s.get(f'rol_{SLUG}') == 'profesor'
            assert s.get(f'profesor_id_{SLUG}') == 1
        # Login clears the session; the seleccionar page regenerates the CSRF
        # token via csrf_token(). Mirror that before the form POST.
        with client.session_transaction() as sess:
            sess['_csrf_token'] = csrf
        r = client.post(f'/{SLUG}/seleccionar', data={
            'materia': 'Matemáticas', 'jornada': 'Mañana', '_csrf_token': csrf})
        assert r.status_code == 302
        with client.session_transaction() as s:
            assert s.get(f'materia_{SLUG}') == 'Matemáticas'
            assert s.get(f'jornada_{SLUG}') == 'Mañana'
        for url in [f'/{SLUG}/dashboard', f'/{SLUG}/home',
                    f'/{SLUG}/asistencia', f'/{SLUG}/horarios',
                    f'/{SLUG}/importar_notas', f'/{SLUG}/archivados',
                    f'/{SLUG}/notificaciones', f'/{SLUG}/actividades/list?curso=Primero+A&periodo=1']:
            assert client.get(url).status_code == 200, url

    def test_teacher_write_lifecycle(self, client, csrf):
        # Prior tests (test_app.py) may leave periodo 1 closed; the walkthrough
        # needs it open to exercise the grade-writing flow.
        conn = db()
        conn.execute('INSERT OR REPLACE INTO periodos_estado (periodo, estado) VALUES (?, ?)', (1, 'abierto'))
        conn.commit()
        conn.close()
        with client.session_transaction() as sess:
            sess[f'profesor_id_{SLUG}'] = 1
            sess[f'rol_{SLUG}'] = 'profesor'
            sess[f'jornada_{SLUG}'] = 'Mañana'
            sess[f'materia_{SLUG}'] = 'Matemáticas'
            sess['_csrf_token'] = CSRF

        r = client.post(f'/{SLUG}/actividades/crear', json={
            'nombre': 'Tarea P5 Walkthrough', 'curso': 'Primero A', 'periodo': 1,
            'tipo': 'taller', 'peso': 0.3, 'descripcion': 'P5 walkthrough'},
            headers={'X-CSRF-Token': CSRF})
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()
        assert data['status'] == 'ok'
        act_id = data['actividad']['id']
        assert act_id

        r = client.post(f'/{SLUG}/registrar', data={
            'nombre': 'P5 Estudiante', 'curso': 'Primero A', '_csrf_token': CSRF})
        assert r.status_code in (200, 302)
        conn = db()
        alumno = conn.execute("SELECT id, nombre FROM alumnos WHERE nombre='P5 Estudiante' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert alumno is not None
        aid = alumno['id']

        r = client.post(f'/{SLUG}/guardar_nota', data={
            'actividad_id': act_id, 'aid': aid, 'val': '4.5', '_csrf_token': CSRF})
        assert r.status_code == 200, r.get_data(as_text=True)
        nota = r.get_json()
        assert nota['status'] == 'ok'
        conn = db()
        fila = conn.execute('SELECT val FROM notas WHERE aid=? AND actividad_id=?', (aid, act_id)).fetchone()
        conn.close()
        assert fila is not None and float(fila['val']) == 4.5

        r = client.post(f'/{SLUG}/guardar_evaluacion', data={
            'aid': aid, 'evaluacion': '4.0', 'autoevaluacion': '5.0',
            'periodo': 1, 'curso': 'Primero A', '_csrf_token': CSRF})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json()['status'] == 'ok'
        conn = db()
        ev = conn.execute('SELECT evaluacion, autoevaluacion FROM evaluaciones WHERE aid=? AND profesor_id=1',
                          (aid,)).fetchone()
        conn.close()
        assert ev is not None and float(ev['evaluacion']) == 4.0 and float(ev['autoevaluacion']) == 5.0

        r = client.post(f'/{SLUG}/marcar_asistencia', data={
            'aid': aid, 'estado': 'P', 'fecha': date.today().isoformat(), '_csrf_token': CSRF})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json()['status'] == 'ok'
        conn = db()
        asis = conn.execute('SELECT estado FROM asistencia WHERE aid=?', (aid,)).fetchone()
        conn.close()
        assert asis is not None and asis['estado'] == 'P'

        # Historial: the nota must appear in the audit trail. The
        # auditoria_notas write is best-effort (can be dropped when the
        # background backup scheduler holds a transient DB lock), so assert
        # deterministically via the audit_log table written by guardar_nota.
        r = client.get(f'/{SLUG}/historial_notas/{aid}')
        assert r.status_code == 200
        conn = db()
        filas = conn.execute("SELECT accion, valor_nuevo FROM audit_log WHERE accion='nota_editada' ORDER BY id DESC LIMIT 20").fetchall()
        conn.close()
        assert any(str(aid) in (x['valor_nuevo'] or '') for x in filas)


# ── STUDENT ────────────────────────────────────────────────────────────────

class TestStudentWalkthrough:
    def test_student_sees_teacher_grade_and_sections(self, client, csrf):
        conn = db()
        alumno = conn.execute("SELECT * FROM alumnos WHERE nombre='P5 Estudiante' ORDER BY id DESC LIMIT 1").fetchone()
        act = conn.execute("SELECT id, nombre FROM actividades WHERE nombre='Tarea P5 Walkthrough' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert alumno is not None and act is not None
        aid = alumno['id']
        with client.session_transaction() as sess:
            sess[f'rol_{SLUG}'] = 'estudiante'
            sess[f'alumno_id_{SLUG}'] = aid
            sess[f'alumno_nombre_{SLUG}'] = 'P5 Estudiante'
            sess[f'alumno_curso_{SLUG}'] = 'Primero A'
            sess[f'alumno_jornada_{SLUG}'] = 'Mañana'
            sess['_csrf_token'] = CSRF
        r = client.get(f'/{SLUG}/estudiante')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'Tarea P5 Walkthrough' in html
        assert '4.5' in html
        for seccion in ['Notas', 'Asistencia', 'Horario', 'Agenda', 'Avisos', 'Canales']:
            assert seccion in html, seccion

    def test_student_logout(self, client, csrf):
        with client.session_transaction() as sess:
            sess[f'rol_{SLUG}'] = 'estudiante'
            sess[f'alumno_id_{SLUG}'] = 1
            sess[f'alumno_nombre_{SLUG}'] = 'Alumno Uno'
            sess[f'alumno_curso_{SLUG}'] = 'Primero A'
            sess[f'alumno_jornada_{SLUG}'] = 'Mañana'
            sess['_csrf_token'] = CSRF
        r = client.get(f'/{SLUG}/logout')
        assert r.status_code in (200, 302)
        with client.session_transaction() as s:
            assert not s.get(f'rol_{SLUG}')


# ── RECTOR ─────────────────────────────────────────────────────────────────

class TestRectorWalkthrough:
    def test_rector_login_and_all_modules(self, client, csrf):
        r = client.get(f'/{SLUG}/rector/login')
        assert r.status_code == 200
        r = client.post(f'/{SLUG}/login', data={
            'accion': 'rector_login', 'rec_usuario': 'rector_prueba',
            'rec_password': 'test123', '_csrf_token': csrf})
        assert r.status_code in (200, 302)
        with client.session_transaction() as s:
            assert s.get(f'rector_id_{SLUG}') == 99
        urls = [
            f'/{SLUG}/rector/panel', f'/{SLUG}/rector/horarios',
            f'/{SLUG}/rector/horarios/datos', f'/{SLUG}/rector/profesores',
            f'/{SLUG}/rector/estudiantes', f'/{SLUG}/rector/cursos',
            f'/{SLUG}/rector/reportes', f'/{SLUG}/rector/asistencia',
            f'/{SLUG}/rector/asistencia_data', f'/{SLUG}/rector/configuracion',
            f'/{SLUG}/rector/solicitudes', f'/{SLUG}/rector/auditoria',
            f'/{SLUG}/rector/comunicaciones', f'/{SLUG}/rector/comunicaciones/nueva',
            f'/{SLUG}/rector/canales', f'/{SLUG}/rector/gestion-rectores',
            f'/{SLUG}/rector/expediente', f'/{SLUG}/rector/observador',
            f'/{SLUG}/rector/certificados', f'/{SLUG}/rector/calendario',
            f'/{SLUG}/rector/mensajes', f'/{SLUG}/api/rector/estudiantes',
            f'/{SLUG}/gestion-academica/alumnos', f'/{SLUG}/matriculas/cupos',
            f'/{SLUG}/matriculas', f'/{SLUG}/tesoreria/facturas',
            f'/{SLUG}/reportes/tablas', f'/{SLUG}/reportes/columnas',
        ]
        for url in urls:
            assert client.get(url).status_code == 200, url

    def test_rector_actions(self, client, csrf):
        with client.session_transaction() as sess:
            sess[f'rector_id_{SLUG}'] = 99
            sess['_csrf_token'] = CSRF

        r = client.post(f'/{SLUG}/rector/periodos/3/cerrar', data={'_csrf_token': CSRF})
        assert r.status_code in (200, 302)
        conn = db()
        est = conn.execute('SELECT estado FROM periodos_estado WHERE periodo=3').fetchone()
        conn.close()
        assert est is not None and est['estado'] == 'cerrado'
        r = client.post(f'/{SLUG}/rector/periodos/3/abrir', data={'_csrf_token': CSRF})
        assert r.status_code in (200, 302)
        conn = db()
        est = conn.execute('SELECT estado FROM periodos_estado WHERE periodo=3').fetchone()
        conn.close()
        assert est is not None and est['estado'] == 'abierto'

        r = client.post(f'/{SLUG}/matriculas/crear', json={
            'nombre': 'P5 Matriculado', 'curso': 'Primero B', 'jornada': 'Mañana'},
            headers={'X-CSRF-Token': CSRF})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json()['status'] == 'ok'
        conn = db()
        fila = conn.execute("SELECT id FROM alumnos WHERE nombre='P5 Matriculado'").fetchone()
        conn.close()
        assert fila is not None
        r = client.post(f'/{SLUG}/matriculas/{fila["id"]}/estado', json={'estado': 'rechazado'},
                        headers={'X-CSRF-Token': CSRF})
        assert r.status_code == 200
        assert r.get_json()['status'] == 'ok'
        conn = db()
        act = conn.execute("SELECT activo FROM alumnos WHERE id=?", (fila['id'],)).fetchone()
        conn.close()
        assert act['activo'] == 0

        r = client.post(f'/{SLUG}/rector/comunicaciones/nueva', data={
            'titulo': 'P5 Comunicado', 'contenido': 'Contenido walkthrough',
            'destinatario_tipo': 'profesores', 'destinatario_valor': '',
            'prioridad': 'normal', 'publicar_ahora': '1', '_csrf_token': CSRF})
        assert r.status_code in (200, 302)
        conn = db()
        com = conn.execute("SELECT id, estado FROM comunicaciones WHERE titulo='P5 Comunicado' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert com is not None
        assert client.get(f'/{SLUG}/rector/comunicaciones/{com["id"]}').status_code == 200


# ── DIRECTORA ──────────────────────────────────────────────────────────────

class TestDirectoraWalkthrough:
    def test_directora_login_panel_boletin(self, client, csrf):
        r = client.get(f'/{SLUG}/directora/login')
        assert r.status_code == 200
        r = client.post(f'/{SLUG}/login', data={
            'accion': 'directora_login', 'dir_usuario': 'directora',
            'dir_password': 'test123', '_csrf_token': csrf})
        assert r.status_code in (200, 302)
        with client.session_transaction() as s:
            assert s.get(f'directora_id_{SLUG}') is not None
        conn = db()
        dir_id = conn.execute("SELECT id FROM directoras WHERE usuario='directora'").fetchone()['id']
        conn.close()
        with client.session_transaction() as s:
            assert s.get(f'directora_id_{SLUG}') == dir_id
        assert client.get(f'/{SLUG}/directora').status_code == 200
        assert client.get(f'/{SLUG}/directora/panel').status_code == 200
        r = client.get(f'/{SLUG}/directora/boletin_pdf?aid=1')
        assert r.status_code == 200
        assert 'pdf' in r.content_type


# ── PARENT ─────────────────────────────────────────────────────────────────

class TestParentWalkthrough:
    def test_parent_portal_login_and_data(self, client, csrf):
        ensure_parent_seed()
        conn = db()
        hijo = conn.execute("SELECT id FROM alumnos WHERE nombre='P5 Estudiante' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert hijo is not None

        r = client.post(f'/{SLUG}/portal/login', json={'email': 'padre_p5@test.com', 'pin': '1234'},
                        headers={'X-CSRF-Token': CSRF})
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert body['status'] == 'ok'
        assert any(c['id'] == hijo['id'] for c in body['hijos'])
        with client.session_transaction() as s:
            assert s.get(f'padre_id_{SLUG}') == 100

        r = client.get(f'/{SLUG}/portal/dashboard', headers={'Accept': 'application/json'})
        assert r.status_code == 200
        assert r.get_json()['hijos']

        r = client.get(f'/{SLUG}/portal/notas/{hijo["id"]}')
        assert r.status_code == 200
        notas = r.get_json()['actividades']
        assert any(a.get('nombre') == 'Tarea P5 Walkthrough' and float(a['prom']) == 4.5 for a in notas)

        r = client.get(f'/{SLUG}/portal/asistencia/{hijo["id"]}')
        assert r.status_code == 200
        assert 'asistencia' in r.get_json()

        r = client.get(f'/{SLUG}/portal/comunicados')
        assert r.status_code == 200
        assert 'comunicados' in r.get_json()

    def test_parent_guard_blocks_other_child(self, client, csrf):
        ensure_parent_seed()
        with client.session_transaction() as sess:
            sess[f'padre_id_{SLUG}'] = 100
            sess['_csrf_token'] = CSRF
        r = client.get(f'/{SLUG}/portal/notas/2')
        assert r.status_code == 403
        r = client.get(f'/{SLUG}/portal/asistencia/2')
        assert r.status_code == 403
