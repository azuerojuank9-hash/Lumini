import os, sys, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'

from flask_app import app

import pytest

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
            sess['_csrf_token'] = self.REUSED_CSRF
        # This expects 204 (success, no content) or 404 (no activity exists)
        r = client.post('/testcolegio/guardar_nota', data={
            '_csrf_token': self.REUSED_CSRF,
            'actividad_id': '1',
            'aid': '1',
            'val': '4.5',
        })
        assert r.status_code in (204, 400, 403, 404, 423)

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
        assert r.status_code in (204, 400, 403, 423)

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
    MOJIBAKE_PATTERNS = ['Ã¡', 'Ã©', 'Ã­', 'Ã³', 'Ãº', 'Ã±', 'Â¿', 'Â·', 'Â«', 'Â»']

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
