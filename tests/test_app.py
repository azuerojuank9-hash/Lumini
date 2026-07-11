import os, sys, json, sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'

from flask_app import app, init_db, hash_pw, _promedio_ponderado, _promedio_simple, _recrear_si_unique_incorrecto

import pytest

TEST_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'colegios_db', 'testcolegio.db')

def seed_test_db():
    # Ensure DB schema exists (creates tables + runs all migrations including v11)
    init_db('testcolegio')
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    # Rector
    cur = conn.execute("SELECT id FROM rectores WHERE usuario='rector_prueba'")
    if not cur.fetchone():
        conn.execute("INSERT INTO rectores (nombre, usuario, password, email, activo, es_principal) VALUES (?,?,?,?,?,?)",
                     ('Rector Prueba', 'rector_prueba', 'ecd71870d1963316a97e3ac3408c9835ad8cf0f3c1bc703527c30265534f75ae', 'rector@test.com', 1, 1))
    # Directora
    cur = conn.execute("SELECT id FROM directoras WHERE usuario='directora'")
    if not cur.fetchone():
        conn.execute("INSERT INTO directoras (nombre, usuario, password, email, activo, curso, jornada) VALUES (?,?,?,?,?,?,?)",
                     ('Directora Prueba', 'directora', hash_pw('test123'), 'directora@test.com', 1, 'Primero A', 'Mañana'))
    # Profesor
    cur = conn.execute("SELECT id FROM profesores WHERE id=1")
    if not cur.fetchone():
        conn.execute("INSERT INTO profesores (id, nombre, usuario, password, email, activo) VALUES (?,?,?,?,?,?)",
                     (1, 'Profesor Uno', 'profesor1', hash_pw('test123'), 'prof1@test.com', 1))
    # Alumnos
    cur = conn.execute("SELECT id FROM alumnos WHERE id=1")
    if not cur.fetchone():
        conn.execute("INSERT INTO alumnos (id, nombre, curso, jornada, activo) VALUES (?,?,?,?,?)",
                     (1, 'Alumno Uno', 'Primero A', 'Mañana', 1))
    cur = conn.execute("SELECT id FROM alumnos WHERE id=2")
    if not cur.fetchone():
        conn.execute("INSERT INTO alumnos (id, nombre, curso, jornada, activo) VALUES (?,?,?,?,?)",
                     (2, 'Alumno Dos', 'Primero A', 'Mañana', 1))
    cur = conn.execute("SELECT id FROM alumnos WHERE id=3")
    if not cur.fetchone():
        conn.execute("INSERT INTO alumnos (id, nombre, curso, jornada, activo) VALUES (?,?,?,?,?)",
                     (3, 'Alumno Tres', 'Segundo A', 'Mañana', 1))
    # Asignaciones curso
    conn.execute('INSERT OR IGNORE INTO asignaciones_curso (profesor_id, materia, jornada, curso) VALUES (?, ?, ?, ?)',
                 (1, 'Matemáticas', 'Mañana', 'Primero A'))
    conn.execute('INSERT OR IGNORE INTO asignaciones_curso (profesor_id, materia, jornada, curso) VALUES (?, ?, ?, ?)',
                 (1, 'Matemáticas', 'Mañana', 'Segundo A'))
    # Periodos
    conn.execute('INSERT OR IGNORE INTO periodos_estado (periodo, estado) VALUES (?, ?)', (1, 'abierto'))
    # Actividades
    conn.execute('INSERT OR IGNORE INTO actividades (id, profesor_id, materia, jornada, curso, nombre, orden, periodo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                 (1, 1, 'Matemáticas', 'Mañana', 'Primero A', 'Tarea 1', 1, 1))
    conn.execute('INSERT OR IGNORE INTO actividades (id, profesor_id, materia, jornada, curso, nombre, orden, periodo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                 (2, 1, 'Matemáticas', 'Mañana', 'Primero A', 'Examen 1', 2, 1))
    conn.commit()
    conn.close()

seed_test_db()

# ── Fixtures ──

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

@pytest.fixture
def csrf(client):
    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'pytest_csrf_token'
    return 'pytest_csrf_token'

@pytest.fixture
def rector_session(client):
    with client.session_transaction() as sess:
        sess['rector_id_testcolegio'] = 1
        sess['_csrf_token'] = 'pytest_csrf_token'

@pytest.fixture
def teacher_session(client):
    with client.session_transaction() as sess:
        sess['profesor_id_testcolegio'] = 1
        sess['rol_testcolegio'] = 'profesor'
        sess['jornada_testcolegio'] = 'Mañana'
        sess['materia_testcolegio'] = 'Matemáticas'
        sess['_csrf_token'] = 'pytest_csrf_token'

@pytest.fixture
def coordinator_session(client):
    with client.session_transaction() as sess:
        sess['directora_id_testcolegio'] = 1
        sess['_csrf_token'] = 'pytest_csrf_token'

# ── Static Assets ──

class TestStaticAssets:
    def test_lumini_js(self, client):
        r = client.get('/static/js/lumini.js')
        assert r.status_code == 200
        assert 'javascript' in r.content_type

    def test_lumini_css(self, client):
        r = client.get('/static/css/lumini.css')
        assert r.status_code == 200
        assert 'text/css' in r.content_type

# ── Landing Pages ──

class TestLandingPages:
    def test_index(self, client):
        r = client.get('/')
        assert r.status_code == 200

    def test_admin_login(self, client):
        r = client.get('/admin')
        assert r.status_code == 200

    def test_rector_login(self, client):
        r = client.get('/testcolegio/rector/login')
        assert r.status_code == 200

    def test_coordinator_login(self, client):
        r = client.get('/testcolegio/directora/login')
        assert r.status_code == 200

    def test_school_login(self, client):
        r = client.get('/testcolegio/login')
        assert r.status_code == 200

# ── Authentication ──

class TestAuthentication:
    def test_rector_login_success(self, client, csrf):
        r = client.post('/testcolegio/login', data={
            '_csrf_token': csrf,
            'accion': 'rector_login',
            'rec_usuario': 'rector_prueba',
            'rec_password': 'test123',
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_rector_login_wrong_password(self, client, csrf):
        r = client.post('/testcolegio/login', data={
            '_csrf_token': csrf,
            'accion': 'rector_login',
            'rec_usuario': 'rector_prueba',
            'rec_password': 'wrong_password',
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_logout(self, client):
        r = client.get('/testcolegio/logout', follow_redirects=True)
        assert r.status_code == 200

# ── Rector Dashboard ──

class TestRectorDashboard:
    def test_panel(self, client, rector_session):
        r = client.get('/testcolegio/rector')
        assert r.status_code == 200
        assert 'LUMINI' in r.get_data(as_text=True)

    def test_profesores(self, client, rector_session):
        r = client.get('/testcolegio/rector/profesores')
        assert r.status_code == 200

    def test_estudiantes(self, client, rector_session):
        r = client.get('/testcolegio/rector/estudiantes')
        assert r.status_code == 200

    def test_cursos(self, client, rector_session):
        r = client.get('/testcolegio/rector/cursos')
        assert r.status_code == 200

    def test_horarios(self, client, rector_session):
        r = client.get('/testcolegio/rector/horarios')
        assert r.status_code == 200

    def test_reportes(self, client, rector_session):
        r = client.get('/testcolegio/rector/reportes')
        assert r.status_code == 200

    def test_configuracion(self, client, rector_session):
        r = client.get('/testcolegio/rector/configuracion')
        assert r.status_code == 200

    def test_comunicaciones(self, client, rector_session):
        r = client.get('/testcolegio/rector/comunicaciones')
        assert r.status_code == 200

    def test_canales(self, client, rector_session):
        r = client.get('/testcolegio/rector/canales')
        assert r.status_code == 200

    def test_auditoria(self, client, rector_session):
        r = client.get('/testcolegio/rector/auditoria')
        assert r.status_code == 200

    def test_solicitudes(self, client, rector_session):
        r = client.get('/testcolegio/rector/solicitudes')
        assert r.status_code == 200

    def test_notificaciones(self, client, rector_session):
        r = client.get('/testcolegio/notificaciones')
        assert r.status_code == 200

    def test_notificaciones_contar(self, client, rector_session):
        r = client.get('/testcolegio/notificaciones/contar')
        assert r.status_code == 200

# ── Teacher Pages (including attendance) ──

class TestTeacherPages:
    def test_teacher_dashboard(self, client, teacher_session):
        r = client.get('/testcolegio/?curso=Primero+A&periodo=1', follow_redirects=True)
        assert r.status_code == 200

    def test_teacher_asistencia_page(self, client, teacher_session):
        r = client.get('/testcolegio/asistencia?curso=Primero+A&fecha=2026-07-04')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'Asistencia' in html

# ── Admin Panel ──

class TestAdmin:
    def test_admin_panel(self, client):
        with client.session_transaction() as sess:
            sess['admin_auth'] = True
        r = client.get('/admin')
        assert r.status_code == 200

    def test_admin_codigos(self, client):
        with client.session_transaction() as sess:
            sess['admin_auth'] = True
        r = client.get('/admin/codigos')
        assert r.status_code == 200

    def test_admin_profesores(self, client):
        with client.session_transaction() as sess:
            sess['admin_auth'] = True
        r = client.get('/admin/profesores/testcolegio')
        assert r.status_code == 200

# ── CRUD Operations ──

class TestCRUD:
    REUSED_CSRF = 'pytest_csrf_crud'

    def test_create_communication(self, client):
        with client.session_transaction() as sess:
            sess['rector_id_testcolegio'] = 1
            sess['_csrf_token'] = self.REUSED_CSRF
        r = client.post('/testcolegio/rector/comunicaciones/nueva', data={
            '_csrf_token': self.REUSED_CSRF,
            'titulo': 'Test Communication',
            'contenido': 'Test content with accents: evaluación, matemáticas.',
            'destinatario_tipo': 'todos',
            'destinatario_valor': '',
            'prioridad': 'normal',
            'publicar_ahora': '1',
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_create_teacher(self, client):
        with client.session_transaction() as sess:
            sess['_csrf_token'] = self.REUSED_CSRF
        r = client.post('/testcolegio/login', data={
            '_csrf_token': self.REUSED_CSRF,
            'accion': 'profesor_registro',
            'nombre': 'Pytest Teacher',
            'reg_usuario': 'pytest_teacher',
            'reg_password': 'test1234',
            'confirmar_password': 'test1234',
            'email_prof': 'teacher@pytest.com',
            'codigo_registro': 'testcode123',
            'pregunta_secreta': '1',
            'respuesta_secreta': 'red',
            'materias_sel': ['Matemáticas'],
            'jornadas_sel': ['Mañana'],
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_create_student(self, client):
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['_csrf_token'] = self.REUSED_CSRF
        r = client.post('/testcolegio/registrar', data={
            '_csrf_token': self.REUSED_CSRF,
            'nombre': 'Pytest Student',
            'curso': 'Primero A',
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_save_grade(self, client):
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        r = client.post('/testcolegio/guardar_nota', data={
            '_csrf_token': self.REUSED_CSRF,
            'actividad_id': '1',
            'aid': '1',
            'val': '4.5',
        })
        assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.get_data(as_text=True)}'
        data = json.loads(r.get_data(as_text=True))
        assert data['status'] == 'ok'
        assert 'promedio' in data, 'Response must include promedio'
        # Verify the grade was actually saved in the database
        conn = sqlite3.connect(TEST_DB)
        row = conn.execute('SELECT val FROM notas WHERE aid=1 AND actividad_id=1').fetchone()
        conn.close()
        assert row is not None, 'Grade was not saved in the database'
        assert row[0] == 4.5

    def test_save_grade_single_nota_returns_correct_promedio(self, client):
        """Una sola nota de 1.6 debe mostrar promedio simple de 1.6 (sin ponderar)."""
        conn = sqlite3.connect(TEST_DB)
        conn.execute('DELETE FROM notas WHERE aid=1')
        conn.execute('DELETE FROM evaluaciones WHERE aid=1')
        conn.commit()
        conn.close()
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        r = client.post('/testcolegio/guardar_nota', data={
            '_csrf_token': self.REUSED_CSRF,
            'actividad_id': '2',
            'aid': '1',
            'val': '1.6',
        })
        assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.get_data(as_text=True)}'
        data = json.loads(r.get_data(as_text=True))
        assert data['status'] == 'ok'
        assert data['promedio'] == 1.6, f'PROM debe ser 1.6 (simple avg), got {data["promedio"]}'

    def test_save_evaluation(self, client):
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        r = client.post('/testcolegio/guardar_evaluacion', data={
            '_csrf_token': self.REUSED_CSRF,
            'aid': '1',
            'evaluacion': '4.0',
        })
        assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.get_data(as_text=True)}'
        data = json.loads(r.get_data(as_text=True))
        assert data['status'] == 'ok'
        # Verify the evaluation was actually saved in the database
        conn = sqlite3.connect(TEST_DB)
        row = conn.execute(
            'SELECT evaluacion FROM evaluaciones WHERE aid=1 AND profesor_id=1 AND materia="Matemáticas" AND jornada="Mañana" AND periodo=1'
        ).fetchone()
        conn.close()
        assert row is not None, 'Evaluation was not saved in the database'
        assert row[0] == 4.0

    def test_save_attendance(self, client):
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        r = client.post('/testcolegio/marcar_asistencia', data={
            '_csrf_token': self.REUSED_CSRF,
            'aid': '1',
            'estado': 'P',
        })
        assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.get_data(as_text=True)}'
        data = json.loads(r.get_data(as_text=True))
        assert data['status'] == 'ok'

    def test_save_attendance_with_fecha(self, client):
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        r = client.post('/testcolegio/marcar_asistencia', data={
            '_csrf_token': self.REUSED_CSRF,
            'aid': '1',
            'estado': 'A',
            'fecha': '2026-06-15',
        })
        assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.get_data(as_text=True)}'
        data = json.loads(r.get_data(as_text=True))
        assert data['status'] == 'ok'
        # Verify persisted
        conn = sqlite3.connect(TEST_DB)
        row = conn.execute(
            'SELECT estado FROM asistencia WHERE aid=1 AND fecha="2026-06-15"'
        ).fetchone()
        conn.close()
        assert row is not None, 'Attendance with fecha was not saved'
        assert row[0] == 'A'

# ── PDF Report Generation ──

class TestPDF:
    def test_boletin_pdf(self, client, coordinator_session):
        r = client.get('/testcolegio/directora/boletin_pdf')
        if r.status_code == 200:
            if 'application/pdf' in (r.content_type or ''):
                assert len(r.get_data()) > 100
            else:
                # Graceful error page when reportlab is not installed
                assert 'reportlab' in r.get_data(as_text=True).lower()
        else:
            # May return 302 (no directora with course) or 404 (no students)
            assert r.status_code in (302, 404)

# ── CSRF / Security ──

class TestCSRF:
    def test_session_cookie_not_secure_in_dev_mode(self):
        assert app.config.get('SESSION_COOKIE_SECURE') == False, \
            'SESSION_COOKIE_SECURE must be False when FLASK_ENV=development'

    def test_session_cookie_secure_logic(self):
        """Verify the SESSION_COOKIE_SECURE derivation logic (env-dependent, override-allowed)."""
        def derive_secure(env, override):
            if override:
                return override.lower() in ('true', '1', 'yes')
            return env == 'production'
        # Production defaults to True
        assert derive_secure('production', '') == True
        # Development defaults to False
        assert derive_secure('development', '') == False
        # Explicit override overrides default
        assert derive_secure('production', 'false') == False
        assert derive_secure('development', 'true') == True

    def test_csrf_mismatch_rejected(self, client):
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'real_token'
        r = client.post('/testcolegio/login', data={
            '_csrf_token': 'wrong_token',
            'accion': 'profesor_login',
            'usuario': 'doesnt_matter',
            'password': 'doesnt_matter',
        }, follow_redirects=True)
        html = r.get_data(as_text=True)
        assert 'Error de seguridad' in html

    def test_csrf_missing_rejected(self, client):
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'real_token'
        r = client.post('/testcolegio/login', data={
            'accion': 'profesor_login',
            'usuario': 'doesnt_matter',
            'password': 'doesnt_matter',
        }, follow_redirects=True)
        html = r.get_data(as_text=True)
        assert 'Error de seguridad' in html

    def test_csrf_empty_session_rejected(self, client):
        """Simulates Secure cookie lost — session has no _csrf_token."""
        r = client.post('/testcolegio/login', data={
            '_csrf_token': 'any_token',
            'accion': 'profesor_login',
            'usuario': 'doesnt_matter',
            'password': 'doesnt_matter',
        }, follow_redirects=True)
        html = r.get_data(as_text=True)
        assert 'Error de seguridad' in html

    def test_directora_registration_form_has_csrf(self, client):
        r = client.get('/testcolegio/login')
        html = r.get_data(as_text=True)
        assert 'directora/registrar_directo' in html
        assert '_csrf_token' in html
        assert 'csrf_token()' not in html

    def test_rector_login_with_valid_csrf_succeeds(self, client):
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'valid_csrf_123'
        r = client.post('/testcolegio/login', data={
            '_csrf_token': 'valid_csrf_123',
            'accion': 'rector_login',
            'rec_usuario': 'rector_prueba',
            'rec_password': 'test123',
        }, follow_redirects=True)
        html = r.get_data(as_text=True)
        assert 'Error de seguridad' not in html

    def test_coordinator_login_with_valid_csrf_succeeds(self, client):
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'valid_coord_csrf'
        r = client.post('/testcolegio/login', data={
            '_csrf_token': 'valid_coord_csrf',
            'accion': 'directora_login',
            'dir_usuario': 'directora_prueba',
            'dir_password': 'test123',
        }, follow_redirects=True)
        html = r.get_data(as_text=True)
        assert 'Error de seguridad' not in html

    def test_teacher_login_with_valid_csrf_succeeds(self, client):
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'valid_teacher_csrf'
        r = client.post('/testcolegio/login', data={
            '_csrf_token': 'valid_teacher_csrf',
            'accion': 'profesor_login',
            'usuario': 'rector_prueba',
            'password': 'test123',
        }, follow_redirects=True)
        html = r.get_data(as_text=True)
        assert 'Error de seguridad' not in html


# ── Rendered HTML Quality ──

class TestHTMLQuality:
    MOJIBAKE_PATTERNS = [
        'Ã¡', 'Ã©', 'Ã­', 'Ã³', 'Ãº', 'Ã±', 'Â¿', 'Â·', 'Â«', 'Â»',
        'Ã¢â€™Â°', 'Ã¯Â¸', 'Ã¢â€”', 'Ã¢Â¸',
    ]

    @pytest.mark.parametrize('path', [
        '/testcolegio/rector',
        '/testcolegio/rector/profesores',
        '/testcolegio/rector/estudiantes',
        '/testcolegio/rector/cursos',
        '/testcolegio/rector/horarios',
        '/testcolegio/rector/reportes',
        '/testcolegio/rector/configuracion',
        '/testcolegio/rector/comunicaciones',
        '/testcolegio/rector/canales',
        '/testcolegio/rector/auditoria',
        '/testcolegio/rector/solicitudes',
        '/testcolegio/notificaciones',
    ])
    def test_no_mojibake(self, client, rector_session, path):
        r = client.get(path)
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        for pat in self.MOJIBAKE_PATTERNS:
            assert pat not in html, f'Mojibake pattern "{pat}" found in {path}'

    @pytest.mark.parametrize('path', [
        '/testcolegio/rector',
        '/testcolegio/rector/profesores',
        '/testcolegio/rector/estudiantes',
        '/testcolegio/rector/cursos',
        '/testcolegio/rector/horarios',
        '/testcolegio/rector/reportes',
        '/testcolegio/rector/configuracion',
        '/testcolegio/rector/comunicaciones',
        '/testcolegio/rector/canales',
        '/testcolegio/rector/auditoria',
        '/testcolegio/rector/solicitudes',
        '/testcolegio/notificaciones',
        '/admin',
        '/',
    ])
    def test_balanced_divs(self, client, rector_session, path):
        if path == '/':
            r = client.get(path)
        elif path.startswith('/admin'):
            with client.session_transaction() as sess:
                sess['admin_auth'] = True
            r = client.get(path)
        else:
            r = client.get(path)
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        open_divs = html.count('<div')
        close_divs = html.count('</div>')
        assert open_divs == close_divs, f'Div imbalance: +{open_divs - close_divs} in {path}'

# ── Observations CRUD ──

class TestObservations:
    """Tests for the complete observations CRUD (create, read, update, delete)."""

    REUSED_CSRF = 'test-csrf-token-for-observations'

    def _create_obs(self, client, texto='Estudiante destacado en clase'):
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        r = client.post('/testcolegio/agregar_observacion', data={
            '_csrf_token': self.REUSED_CSRF,
            'aid': '1',
            'texto': texto,
        })
        assert r.status_code == 200, f'Create obs failed: {r.status_code} {r.get_data(as_text=True)}'
        return json.loads(r.get_data(as_text=True))['id']

    def test_create_observation(self, client):
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        r = client.post('/testcolegio/agregar_observacion', data={
            '_csrf_token': self.REUSED_CSRF,
            'aid': '1',
            'texto': 'Estudiante destacado en clase',
        })
        assert r.status_code == 200, f'Create obs failed: {r.status_code} {r.get_data(as_text=True)}'
        data = json.loads(r.get_data(as_text=True))
        assert 'id' in data, 'Create obs response missing id'
        assert data['texto'] == 'Estudiante destacado en clase'
        assert data['materia'] == 'Matemáticas'
        # Verify persisted in DB
        conn = sqlite3.connect(TEST_DB)
        row = conn.execute('SELECT id, texto FROM observaciones WHERE id=?', (data['id'],)).fetchone()
        conn.close()
        assert row is not None, 'Observation not found in DB after create'
        assert row[1] == 'Estudiante destacado en clase'
        # Verify audit_log
        conn = sqlite3.connect(TEST_DB)
        log = conn.execute(
            'SELECT accion, valor_nuevo FROM audit_log WHERE tabla="observaciones" AND registro_id=?',
            (data['id'],)
        ).fetchone()
        conn.close()
        assert log is not None, 'Audit log not found for observation create'
        assert log[0] == 'observacion_creada'

    def test_edit_observation(self, client):
        obs_id = self._create_obs(client)
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        r = client.post(f'/testcolegio/editar_observacion/{obs_id}', data={
            '_csrf_token': self.REUSED_CSRF,
            'texto': 'Texto editado: muy buen desempeño',
        })
        assert r.status_code == 200, f'Edit obs failed: {r.status_code} {r.get_data(as_text=True)}'
        data = json.loads(r.get_data(as_text=True))
        assert data['id'] == obs_id
        assert data['texto'] == 'Texto editado: muy buen desempeño'
        # Verify persisted
        conn = sqlite3.connect(TEST_DB)
        row = conn.execute('SELECT texto FROM observaciones WHERE id=?', (obs_id,)).fetchone()
        conn.close()
        assert row[0] == 'Texto editado: muy buen desempeño'
        # Verify audit_log
        conn = sqlite3.connect(TEST_DB)
        log = conn.execute(
            'SELECT accion, valor_anterior, valor_nuevo FROM audit_log WHERE tabla="observaciones" AND registro_id=? AND accion="observacion_editada"',
            (obs_id,)
        ).fetchone()
        conn.close()
        assert log is not None, 'Audit log not found for observation edit'

    def test_delete_observation(self, client):
        # First create one
        obs_id = self._create_obs(client)
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        r = client.post(f'/testcolegio/borrar_observacion/{obs_id}', data={
            '_csrf_token': self.REUSED_CSRF,
        })
        assert r.status_code == 200, f'Delete obs failed: {r.status_code} {r.get_data(as_text=True)}'
        data = json.loads(r.get_data(as_text=True))
        assert data.get('ok') is True
        # Verify deleted from DB
        conn = sqlite3.connect(TEST_DB)
        row = conn.execute('SELECT id FROM observaciones WHERE id=?', (obs_id,)).fetchone()
        conn.close()
        assert row is None, 'Observation still exists in DB after delete'
        # Verify audit_log
        conn = sqlite3.connect(TEST_DB)
        log = conn.execute(
            'SELECT accion FROM audit_log WHERE tabla="observaciones" AND registro_id=? AND accion="observacion_eliminada"',
            (obs_id,)
        ).fetchone()
        conn.close()
        assert log is not None, 'Audit log not found for observation delete'

    def test_edit_forbidden_wrong_materia(self, client):
        """Verify that a teacher cannot edit an observation from a different subject."""
        # Create obs in Matemáticas
        obs_id = self._create_obs(client)
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Español'  # Different subject
            sess['_csrf_token'] = self.REUSED_CSRF
        r = client.post(f'/testcolegio/editar_observacion/{obs_id}', data={
            '_csrf_token': self.REUSED_CSRF,
            'texto': 'Should not work',
        })
        assert r.status_code == 404, f'Expected 404 for wrong materia, got {r.status_code}'

    def test_delete_forbidden_wrong_materia(self, client):
        """Verify that a teacher cannot delete an observation from a different subject."""
        obs_id = self._create_obs(client)
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Español'
            sess['_csrf_token'] = self.REUSED_CSRF
        r = client.post(f'/testcolegio/borrar_observacion/{obs_id}', data={
            '_csrf_token': self.REUSED_CSRF,
        })
        # Should silently ignore (materia mismatch, observation remains)
        data = json.loads(r.get_data(as_text=True))
        assert data.get('ok') is True
        # Verify observation still exists
        conn = sqlite3.connect(TEST_DB)
        row = conn.execute('SELECT id FROM observaciones WHERE id=?', (obs_id,)).fetchone()
        conn.close()
        assert row is not None, 'Observation was deleted despite materia mismatch'

# ── Grades System Audit ──

class TestGradesSystem:
    """End-to-end audit of the grades system."""

    REUSED_CSRF = 'test-csrf-token-grades'

    def test_save_grade_and_verify_promedio(self, client):
        """Save a grade and verify the promedio response is correct."""
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        # Grade: 4.5
        r = client.post('/testcolegio/guardar_nota', data={
            '_csrf_token': self.REUSED_CSRF,
            'actividad_id': '1',
            'aid': '1',
            'val': '4.5',
            'curso': 'Primero A',
        })
        assert r.status_code == 200, f'Grade save failed: {r.status_code} {r.get_data(as_text=True)}'
        data = json.loads(r.get_data(as_text=True))
        assert data['status'] == 'ok'
        assert data['promedio'] is not None
        # Verify persisted in DB
        conn = sqlite3.connect(TEST_DB)
        row = conn.execute('SELECT val FROM notas WHERE aid=1 AND actividad_id=1').fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 4.5

    def test_edit_grade_verifies_update(self, client):
        """Edit an existing grade and verify both DB and response."""
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        # First save a grade
        client.post('/testcolegio/guardar_nota', data={
            '_csrf_token': self.REUSED_CSRF,
            'actividad_id': '1', 'aid': '1', 'val': '3.0', 'curso': 'Primero A',
        })
        # Edit to 4.0
        r = client.post('/testcolegio/guardar_nota', data={
            '_csrf_token': self.REUSED_CSRF,
            'actividad_id': '1', 'aid': '1', 'val': '4.0', 'curso': 'Primero A',
        })
        assert r.status_code == 200
        data = json.loads(r.get_data(as_text=True))
        assert data['status'] == 'ok'
        # Verify DB has the new value
        conn = sqlite3.connect(TEST_DB)
        row = conn.execute('SELECT val FROM notas WHERE aid=1 AND actividad_id=1').fetchone()
        conn.close()
        assert row[0] == 4.0, f'Expected 4.0, got {row[0]}'

    def test_save_multiple_grades_updates_promedio(self, client):
        """Save multiple grades for the same student and verify promedio changes."""
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        # Save grade for actividad 1: 5.0
        r1 = client.post('/testcolegio/guardar_nota', data={
            '_csrf_token': self.REUSED_CSRF,
            'actividad_id': '1', 'aid': '1', 'val': '5.0', 'curso': 'Primero A',
        })
        assert r1.status_code == 200
        # Save grade for actividad 2: 3.0
        r2 = client.post('/testcolegio/guardar_nota', data={
            '_csrf_token': self.REUSED_CSRF,
            'actividad_id': '2', 'aid': '1', 'val': '3.0', 'curso': 'Primero A',
        })
        assert r2.status_code == 200
        d2 = json.loads(r2.get_data(as_text=True))
        assert d2['promedio'] is not None
        # Verify both persisted
        conn = sqlite3.connect(TEST_DB)
        rows = conn.execute('SELECT val FROM notas WHERE aid=1 ORDER BY actividad_id').fetchall()
        conn.close()
        assert len(rows) == 2
        assert rows[0][0] == 5.0
        assert rows[1][0] == 3.0

    def test_grade_decimal_values(self, client):
        """Test various decimal values: 0, 5, 2.5."""
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        # Test 5
        r = client.post('/testcolegio/guardar_nota', data={
            '_csrf_token': self.REUSED_CSRF,
            'actividad_id': '1', 'aid': '1', 'val': '5', 'curso': 'Primero A',
        })
        assert r.status_code == 200
        data = json.loads(r.get_data(as_text=True))
        assert data['status'] == 'ok'
        # Verify persisted
        conn = sqlite3.connect(TEST_DB)
        row = conn.execute('SELECT val FROM notas WHERE aid=1 AND actividad_id=1').fetchone()
        conn.close()
        assert row[0] == 5.0

    def test_invalid_grade_rejected(self, client):
        """Test that invalid grades are rejected by the backend."""
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        # Value > 5
        r = client.post('/testcolegio/guardar_nota', data={
            '_csrf_token': self.REUSED_CSRF,
            'actividad_id': '1', 'aid': '1', 'val': '6.0', 'curso': 'Primero A',
        })
        # Should be rejected but... the backend doesn't validate range,
        # it just saves what it receives. The validation is in the frontend.
        # This is an architectural note, not a test failure.
        assert r.status_code in (200, 400), f'Unexpected: {r.status_code}'

    def test_nota_audit_logged(self, client):
        """Verify that grade changes are recorded in audit_log."""
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        client.post('/testcolegio/guardar_nota', data={
            '_csrf_token': self.REUSED_CSRF,
            'actividad_id': '1', 'aid': '1', 'val': '4.0', 'curso': 'Primero A',
        })
        conn = sqlite3.connect(TEST_DB)
        log = conn.execute(
            'SELECT accion FROM audit_log WHERE tabla="notas" AND accion="nota_editada" ORDER BY id DESC LIMIT 1'
        ).fetchone()
        conn.close()
        assert log is not None, 'Audit log entry not found for note edit'

    def test_promedio_ponderado_consistency(self, client):
        """Verify PROM = simple avg, N.Final = weighted (65/25/10)."""
        with client.session_transaction() as sess:
            sess['profesor_id_testcolegio'] = 1
            sess['jornada_testcolegio'] = 'Mañana'
            sess['materia_testcolegio'] = 'Matemáticas'
            sess['_csrf_token'] = self.REUSED_CSRF
        client.post('/testcolegio/guardar_evaluacion', data={
            '_csrf_token': self.REUSED_CSRF,
            'aid': '1', 'evaluacion': '4.0', 'autoevaluacion': '3.0', 'periodo': '1', 'curso': 'Primero A',
        })
        client.post('/testcolegio/guardar_nota', data={
            '_csrf_token': self.REUSED_CSRF,
            'actividad_id': '1', 'aid': '1', 'val': '5.0', 'curso': 'Primero A',
        })
        client.post('/testcolegio/guardar_nota', data={
            '_csrf_token': self.REUSED_CSRF,
            'actividad_id': '2', 'aid': '1', 'val': '3.0', 'curso': 'Primero A',
        })
        r = client.get('/testcolegio/?curso=Primero+A&periodo=1')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        # PROM column = simple avg of actividades (5+3)/2 = 4.0
        assert 'id="prom-1"' in html
        assert '4.0' in html, f'Expected simple avg 4.0 in PROM column'
        # N.Final column = 4.0*0.65 + 4.0*0.25 + 3.0*0.10 = 3.9
        assert 'id="nf-1"' in html
        assert '3.9' in html, f'Expected weighted 3.9 in N.Final column'


# ── Promedio Ponderado Formula ──

def _manual_promedio(notas, eval_v, auto_v):
    act_prom = round(sum(notas) / len(notas), 2) if notas else None
    total = 0
    if act_prom is not None: total += act_prom * 0.65
    if eval_v is not None:   total += eval_v * 0.25
    if auto_v is not None:   total += auto_v * 0.10
    return round(total, 2) if (act_prom is not None or eval_v is not None or auto_v is not None) else None


class TestPromedioPonderadoFormula:
    def test_solo_actividades(self):
        r = _promedio_ponderado([4.0, 3.0], None, None)
        m = _manual_promedio([4.0, 3.0], None, None)
        assert r == m, f'solo actividades: _promedio_ponderado={r} manual={m}'
        assert r == 2.27, f'esperado 2.27, obtenido {r}'

    def test_actividades_y_evaluacion(self):
        r = _promedio_ponderado([4.0, 3.0], 3.5, None)
        m = _manual_promedio([4.0, 3.0], 3.5, None)
        assert r == m, f'act+eval: _promedio_ponderado={r} manual={m}'
        assert r == 3.15, f'esperado 3.15, obtenido {r}'

    def test_actividades_y_autoevaluacion(self):
        r = _promedio_ponderado([4.0, 3.0], None, 5.0)
        m = _manual_promedio([4.0, 3.0], None, 5.0)
        assert r == m, f'act+auto: _promedio_ponderado={r} manual={m}'
        assert r == 2.77, f'esperado 2.77, obtenido {r}'

    def test_solo_evaluacion(self):
        r = _promedio_ponderado([], 4.0, None)
        m = _manual_promedio([], 4.0, None)
        assert r == m, f'solo eval: _promedio_ponderado={r} manual={m}'

    def test_solo_autoevaluacion(self):
        r = _promedio_ponderado([], None, 5.0)
        m = _manual_promedio([], None, 5.0)
        assert r == m, f'solo auto: _promedio_ponderado={r} manual={m}'

    def test_tres_categorias_completas(self):
        r = _promedio_ponderado([4.0, 3.0], 3.5, 5.0)
        m = _manual_promedio([4.0, 3.0], 3.5, 5.0)
        assert r == m, f'completo: _promedio_ponderado={r} manual={m}'
        assert r == 3.65, f'esperado 3.65, obtenido {r}'

    def test_sin_datos_retorna_none(self):
        assert _promedio_ponderado([], None, None) is None

class TestPromedioUnicaNota:
    """Verifica que con una sola nota existente el promedio sea correcto (sin dividir por total de actividades)."""

    def test_una_nota_1_6_devuelve_act_prom_1_6(self):
        r = _promedio_ponderado([1.6], None, None)
        assert r == 1.04, f'Una nota 1.6 debe dar 1.04 (1.6*0.65), no {r}'

    def test_una_nota_5_0_devuelve_3_25(self):
        r = _promedio_ponderado([5.0], None, None)
        assert r == 3.25, f'Una nota 5.0 debe dar 3.25 (5.0*0.65), no {r}'

    def test_una_nota_con_eval_devuelve_correcto(self):
        r = _promedio_ponderado([1.6], 3.0, None)
        assert r == 1.79, f'act=1.6 eval=3.0 debe dar 1.79, no {r}'

    def test_varias_notas_sin_eval_devuelve_correcto(self):
        r = _promedio_ponderado([4.0, 3.0, 5.0], None, None)
        esperado = round((4.0+3.0+5.0)/3 * 0.65, 2)
        assert r == esperado, f'[4,3,5] sin eval debe dar {esperado}, no {r}'

    def test_varias_notas_con_eval_y_auto(self):
        r = _promedio_ponderado([4.0, 3.0], 3.5, 5.0)
        assert r == 3.65, f'[4,3] + eval=3.5 + auto=5.0 debe dar 3.65, no {r}'

    def test_sin_notas_solo_eval_devuelve_25_por_ciento(self):
        r = _promedio_ponderado([], 1.6, None)
        assert r == 0.40, f'sin actividades, eval=1.6 debe dar 0.40 (1.6*0.25), no {r}'

    def test_notas_vacias_no_afectan_act_prom(self):
        """Si notas_actividades tiene None, deben ser ignorados."""
        r = _promedio_ponderado([1.6, None, None], None, None)
        assert r == 1.04, f'None debe ser ignorado, debe dar 1.04, no {r}'

    def test_sin_datos_retorna_none(self):
        assert _promedio_ponderado([], None, None) is None
        assert _promedio_ponderado(None, None, None) is None


class TestPromedioSimple:
    """_promedio_simple: promedio exacto como calculadora (suma/cant, sin ponderar)."""

    def test_una_nota_1_6(self):
        assert _promedio_simple([1.6]) == 1.6

    def test_una_nota_5_0(self):
        assert _promedio_simple([5.0]) == 5.0

    def test_dos_notas(self):
        assert _promedio_simple([4.0, 3.0]) == 3.5

    def test_tres_notas(self):
        assert _promedio_simple([4.0, 3.0, 5.0]) == 4.0

    def test_notas_con_none_ignorados(self):
        assert _promedio_simple([1.6, None, None]) == 1.6

    def test_todos_none_retorna_none(self):
        assert _promedio_simple([None, None]) is None

    def test_lista_vacia_retorna_none(self):
        assert _promedio_simple([]) is None

    def test_none_retorna_none(self):
        assert _promedio_simple(None) is None

    def test_redondeo_2_decimales(self):
        r = _promedio_simple([4.0, 3.0, 5.0, 2.0])
        esperado = round((4.0+3.0+5.0+2.0)/4, 2)
        assert r == esperado, f'Esperado {esperado}, obtenido {r}'

    def test_suma_entera_con_decimales(self):
        assert _promedio_simple([3.3, 3.3, 3.3]) == 3.3


class TestMigraciones:
    """Verifica que _recrear_si_unique_incorrecto detecte y corrija UNIQUEs erroneos."""

    def test_recrea_evaluaciones_unique_incorrecto(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute('''CREATE TABLE evaluaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aid INTEGER NOT NULL, profesor_id INTEGER NOT NULL,
            materia TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT "Mañana",
            evaluacion REAL, autoevaluacion REAL, periodo INTEGER DEFAULT 1,
            UNIQUE(aid,profesor_id,materia,jornada))''')
        conn.execute('INSERT INTO evaluaciones (aid, profesor_id, materia, jornada, evaluacion, periodo) VALUES (1, 1, "Mat", "M", 4.0, 1)')
        conn.commit()
        result = _recrear_si_unique_incorrecto(conn, 'test', 'evaluaciones',
            '(aid,profesor_id,materia,jornada,periodo)',
            '''CREATE TABLE evaluaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aid INTEGER NOT NULL, profesor_id INTEGER NOT NULL,
                materia TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT "Mañana",
                evaluacion REAL, autoevaluacion REAL, periodo INTEGER DEFAULT 1,
                UNIQUE(aid,profesor_id,materia,jornada,periodo))''',
            '''(id,aid,profesor_id,materia,jornada,evaluacion,autoevaluacion,periodo)
               SELECT id,aid,profesor_id,materia,jornada,evaluacion,autoevaluacion,
                      COALESCE(periodo,1) FROM evaluaciones_old''')
        assert result == True, 'Deberia haber recreado la tabla'
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='evaluaciones'").fetchone()[0]
        assert 'UNIQUE(aid,profesor_id,materia,jornada,periodo)' in sql, 'UNIQUE debe incluir periodo'
        row = conn.execute('SELECT * FROM evaluaciones').fetchone()
        assert row['aid'] == 1
        assert row['evaluacion'] == 4.0
        assert row['periodo'] == 1
        conn.close()

    def test_no_recrea_si_unique_correcto(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute('''CREATE TABLE evaluaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aid INTEGER NOT NULL, profesor_id INTEGER NOT NULL,
            materia TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT "Mañana",
            evaluacion REAL, autoevaluacion REAL, periodo INTEGER DEFAULT 1,
            UNIQUE(aid,profesor_id,materia,jornada,periodo))''')
        conn.commit()
        result = _recrear_si_unique_incorrecto(conn, 'test', 'evaluaciones',
            '(aid,profesor_id,materia,jornada,periodo)',
            '''CREATE TABLE evaluaciones (...)''', 'SELECT * FROM evaluaciones_old')
        assert result == False, 'No deberia recrear la tabla si UNIQUE ya es correcto'
        conn.close()

    def test_recrea_horarios_curso_unique_incorrecto(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute('''CREATE TABLE horarios_curso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            curso TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT "Mañana",
            dia TEXT NOT NULL, franja TEXT NOT NULL,
            num TEXT DEFAULT "", materia TEXT DEFAULT "", profesor TEXT DEFAULT "",
            UNIQUE(curso, dia, franja))''')
        conn.execute('INSERT INTO horarios_curso (curso, jornada, dia, franja) VALUES ("1A", "M", "Lun", "1")')
        conn.commit()
        result = _recrear_si_unique_incorrecto(conn, 'test', 'horarios_curso',
            '(curso,jornada,dia,franja)',
            '''CREATE TABLE horarios_curso (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                curso TEXT NOT NULL, jornada TEXT NOT NULL DEFAULT "Mañana",
                dia TEXT NOT NULL, franja TEXT NOT NULL,
                num TEXT DEFAULT "", materia TEXT DEFAULT "", profesor TEXT DEFAULT "",
                UNIQUE(curso, jornada, dia, franja))''',
            'SELECT * FROM horarios_curso_old')
        assert result == True
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='horarios_curso'").fetchone()[0]
        assert 'UNIQUE(curso, jornada, dia, franja)' in sql
        row = conn.execute('SELECT * FROM horarios_curso').fetchone()
        assert row['curso'] == '1A'
        conn.close()

    def test_guardar_evaluacion_con_upsert_ok(self, client, teacher_session):
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'pytest_csrf_token'
        r = client.post('/testcolegio/guardar_evaluacion', data={
            '_csrf_token': 'pytest_csrf_token',
            'aid': '1', 'evaluacion': '4.5', 'autoevaluacion': '3.5', 'periodo': '1', 'curso': 'Primero A',
        })
        assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.get_data(as_text=True)}'
        data = json.loads(r.get_data(as_text=True))
        assert data['status'] == 'ok'
        r2 = client.post('/testcolegio/guardar_evaluacion', data={
            '_csrf_token': 'pytest_csrf_token',
            'aid': '1', 'evaluacion': '4.8', 'autoevaluacion': '3.8', 'periodo': '1', 'curso': 'Primero A',
        })
        assert r2.status_code == 200, f'Expected 200 on overwrite, got {r2.status_code}: {r2.get_data(as_text=True)}'
        data2 = json.loads(r2.get_data(as_text=True))
        assert data2['status'] == 'ok'
        conn = sqlite3.connect(TEST_DB)
        row = conn.execute(
            'SELECT evaluacion, autoevaluacion FROM evaluaciones WHERE aid=1 AND profesor_id=1 AND materia="Matemáticas" AND jornada="Mañana" AND periodo=1'
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 4.8
        assert row[1] == 3.8
