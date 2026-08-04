"""P4 — Navegación y visuales en todos los roles.

Asserts the P4 navigation/visuals work:
  - Estado activo del sidebar por prefijo más largo (funciona en subpáginas).
  - Breadcrumbs presentes en Panel del docente, Panel de la directora y
    Mi Boletín del estudiante.
  - El portal del padre hereda el modo oscuro (bloque CSS data-theme).
  - Páginas clave no muestran texto visible en inglés.
"""

import os
import re
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
CSRF = 'p4_nav_csrf'

# Fragmento JS de estado activo por prefijo más largo presente en los 3 sidebars.
ACTIVE_JS = "p.indexOf(h+'/')===0"


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


def _teacher_session(client):
    with client.session_transaction() as sess:
        sess[f'profesor_id_{SLUG}'] = 1
        sess[f'rol_{SLUG}'] = 'profesor'
        sess[f'jornada_{SLUG}'] = 'Mañana'
        sess[f'materia_{SLUG}'] = 'Matemáticas'
        sess['_csrf_token'] = CSRF


def _directora_session(client):
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    dir_id = conn.execute("SELECT id FROM directoras WHERE usuario='directora'").fetchone()['id']
    conn.close()
    with client.session_transaction() as sess:
        sess[f'directora_id_{SLUG}'] = dir_id
        sess['_csrf_token'] = CSRF


def _rector_session(client):
    with client.session_transaction() as sess:
        sess[f'rector_id_{SLUG}'] = 99
        sess['_csrf_token'] = CSRF


def _estudiante_session(client):
    with client.session_transaction() as sess:
        sess[f'rol_{SLUG}'] = 'estudiante'
        sess[f'alumno_id_{SLUG}'] = 1
        sess[f'alumno_nombre_{SLUG}'] = 'Alumno Uno'
        sess[f'alumno_curso_{SLUG}'] = 'Primero A'
        sess[f'alumno_jornada_{SLUG}'] = 'Mañana'
        sess['_csrf_token'] = CSRF


def _padre_session(client):
    with client.session_transaction() as sess:
        sess[f'padre_id_{SLUG}'] = 101
        sess['_csrf_token'] = CSRF


def _seed_padre():
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    conn.execute('INSERT OR IGNORE INTO padres (id, nombre, email, pin, activo) VALUES (?,?,?,?,?)',
                 (101, 'Padre P4', 'padre_p4@test.com', '1234', 1))
    conn.execute('INSERT OR IGNORE INTO alumno_padre (padre_id, alumno_id) VALUES (?,?)', (101, 1))
    conn.commit()
    conn.close()


class TestSidebarActivo:
    def test_teacher_home_incluye_js_prefijo_largo(self, client, csrf):
        _teacher_session(client)
        r = client.get(f'/{SLUG}/')
        assert r.status_code == 200
        assert ACTIVE_JS in r.get_data(as_text=True)

    def test_directora_panel_incluye_js_prefijo_largo(self, client, csrf):
        _directora_session(client)
        r = client.get(f'/{SLUG}/directora/panel')
        assert r.status_code == 200
        assert ACTIVE_JS in r.get_data(as_text=True)

    def test_rector_panel_incluye_js_prefijo_largo(self, client, csrf):
        _rector_session(client)
        r = client.get(f'/{SLUG}/rector/panel')
        assert r.status_code == 200
        assert ACTIVE_JS in r.get_data(as_text=True)


class TestBreadcrumbs:
    def test_dashboard_profesor_tiene_breadcrumb(self, client, csrf):
        _teacher_session(client)
        r = client.get(f'/{SLUG}/dashboard')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'breadcrumb' in html and 'Ruta de navegaci' in html
        assert 'Panel del Docente' in html

    def test_directora_panel_tiene_breadcrumb(self, client, csrf):
        _directora_session(client)
        r = client.get(f'/{SLUG}/directora/panel')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'breadcrumb' in html and 'Ruta de navegaci' in html

    def test_estudiante_tiene_breadcrumb(self, client, csrf):
        _estudiante_session(client)
        r = client.get(f'/{SLUG}/estudiante')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'breadcrumb' in html and 'Ruta de navegaci' in html


class TestModoOscuroPortalPadre:
    def test_portal_padre_tiene_css_oscuro(self, client, csrf):
        r = client.get(f'/{SLUG}/portal/login')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'data-theme="dark"' in html
        assert 'html[data-theme="dark"] .pp-login' in html

    def test_portal_padre_dashboard_incluye_css_oscuro(self, client, csrf):
        _seed_padre()
        _padre_session(client)
        r = client.get(f'/{SLUG}/portal/dashboard', headers={'Accept': 'text/html'})
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'html[data-theme="dark"]' in html


class TestPortalPadreSesionAlRecargar:
    """Al recargar /portal/login con sesión válida debe verse el dashboard,
    no el formulario de login; tras cerrar sesión vuelve el formulario."""

    def _seed(self):
        _seed_padre()
        conn = sqlite3.connect(TEST_DB)
        conn.row_factory = sqlite3.Row
        conn.execute('DELETE FROM padres WHERE id=101')
        conn.execute('INSERT INTO padres (id, nombre, email, pin, activo) VALUES (?,?,?,?,?)',
                     (101, 'Padre Recarga', 'recarga@test.com', '7777', 1))
        conn.execute('INSERT OR IGNORE INTO alumno_padre (padre_id, alumno_id) VALUES (?,?)', (101, 1))
        conn.commit()
        conn.close()

    def test_sin_sesion_muestra_formulario(self, client, csrf):
        self._seed()
        r = client.get(f'/{SLUG}/portal/login')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'id="ppLogin" class="pp-login" style="display:block;"' in html
        assert 'id="ppDashboard" class="pp-dash" style="display:none;"' in html

    def test_reload_con_sesion_muestra_dashboard_directamente(self, client, csrf):
        self._seed()
        _padre_session(client)
        r = client.get(f'/{SLUG}/portal/login')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'id="ppLogin" class="pp-login" style="display:none;"' in html
        assert 'id="ppDashboard" class="pp-dash" style="display:block;"' in html
        assert 'Bienvenido, ' in html and 'Padre Recarga' in html
        tail = html.split('function escJsStr')[1].split('</script>')[0]
        assert 'renderHijos(' in tail and 'ppLogin(' not in tail

    def test_dashboard_html_precarga_hijos(self, client, csrf):
        self._seed()
        _padre_session(client)
        r = client.get(f'/{SLUG}/portal/dashboard', headers={'Accept': 'text/html'})
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'id="ppLogin" class="pp-login" style="display:none;"' in html
        assert 'id="ppDashboard" class="pp-dash" style="display:block;"' in html
        assert 'renderHijos(' in html and 'Alumno Uno' in html

    def test_logout_vuelve_al_formulario(self, client, csrf):
        self._seed()
        _padre_session(client)
        r = client.get(f'/{SLUG}/logout')
        assert r.status_code in (301, 302)
        r = client.get(f'/{SLUG}/portal/login')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'id="ppLogin" class="pp-login" style="display:block;"' in html
        assert 'id="ppDashboard" class="pp-dash" style="display:none;"' in html


class TestTitulosEnEspanol:
    """El texto visible del título (pestaña del navegador) debe ser español."""
    PAGES = [
        ('teacher', '/{s}/'),
        ('teacher', '/{s}/dashboard'),
        ('rector', '/{s}/rector/panel'),
        ('directora', '/{s}/directora/panel'),
    ]
    BANNED = ['Dashboard', 'Login', 'Email', 'Password', 'Logout', 'Student', 'Profile']

    @pytest.mark.parametrize('role,path_tpl', PAGES)
    def test_titulo_visible_en_espanol(self, client, csrf, role, path_tpl):
        {'teacher': _teacher_session, 'rector': _rector_session,
         'directora': _directora_session}[role](client)
        r = client.get(path_tpl.format(s=SLUG))
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        m = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
        assert m, f'sin <title> en {path_tpl}'
        title = m.group(1).strip()
        assert title, f'<title> vacío en {path_tpl}'
        for word in self.BANNED:
            assert word not in title, f'{word} aparece en el título de {path_tpl}: {title}'
