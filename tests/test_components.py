import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'
import pytest

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')

@pytest.fixture
def env():
    from jinja2 import Environment, FileSystemLoader
    return Environment(loader=FileSystemLoader(TEMPLATE_DIR))

def tmpl(env, src):
    return env.from_string(src).render()

class TestSidebarComponent:
    def test_sidebar_item_active(self, env):
        html = tmpl(env, '{% from "components.html" import sidebar_item %}{{ sidebar_item("/test", "home", "Inicio", active=true) }}')
        assert 'sidebar-item active' in html
        assert 'aria-current="page"' in html
        assert '/test' in html

    def test_sidebar_item_with_count(self, env):
        html = tmpl(env, '{% from "components.html" import sidebar_item %}{{ sidebar_item("/test", "bell", "Notif", count=5) }}')
        assert 'badge-count' in html
        assert '5' in html

class TestCardComponent:
    def test_card_renders(self, env):
        html = tmpl(env, '{% from "components.html" import card %}{{ card("Titulo", "Cuerpo") }}')
        assert 'card' in html
        assert 'Titulo' in html
        assert 'Cuerpo' in html

    def test_card_no_body(self, env):
        html = tmpl(env, '{% from "components.html" import card %}{{ card("Solo titulo") }}')
        assert 'Solo titulo' in html

class TestBadgeComponent:
    def test_badge_renders(self, env):
        html = tmpl(env, '{% from "components.html" import badge %}{{ badge("Activo", "success") }}')
        assert 'badge-success' in html
        assert 'Activo' in html

    def test_status_badge_mapping(self, env):
        html = tmpl(env, '{% from "components.html" import status_badge %}{{ status_badge("publicado") }}')
        assert 'badge-success' in html

class TestAlertComponent:
    def test_alert_error(self, env):
        html = tmpl(env, '{% from "components.html" import alert_error %}{{ alert_error("Algo salio mal") }}')
        assert 'alert-error' in html
        assert 'Algo salio mal' in html

    def test_alert_success(self, env):
        html = tmpl(env, '{% from "components.html" import alert_success %}{{ alert_success("Operacion exitosa") }}')
        assert 'alert-success' in html
        assert 'Operacion exitosa' in html

class TestButtonComponent:
    def test_btn_as_link(self, env):
        html = tmpl(env, '{% from "components.html" import btn %}{{ btn(url="/test", label="Click", class="btn-primary", icon="plus") }}')
        assert 'href="/test"' in html
        assert 'btn-primary' in html

    def test_btn_as_button(self, env):
        html = tmpl(env, '{% from "components.html" import btn %}{{ btn(label="Enviar", class="btn-primary", type="submit") }}')
        assert 'type="submit"' in html
        assert 'Enviar' in html

class TestModalComponent:
    def test_modal_renders(self, env):
        html = tmpl(env, '{% from "components.html" import modal %}{{ modal("test-modal", "Confirmar", "Esta seguro?") }}')
        assert 'test-modal' in html
        assert 'Confirmar' in html

class TestEmptyStateComponent:
    def test_empty_state_renders(self, env):
        html = tmpl(env, '{% from "components.html" import empty_state %}{{ empty_state("inbox", "Sin datos", "No hay registros") }}')
        assert 'Sin datos' in html
        assert 'No hay registros' in html

class TestStatsCardComponent:
    def test_stats_card_renders(self, env):
        html = tmpl(env, '{% from "components.html" import stats_card %}{{ stats_card("150", "Estudiantes", "users", "purple") }}')
        assert 'stats-card' in html
        assert '150' in html
        assert 'Estudiantes' in html

class TestPaginationComponent:
    def test_pagination_renders(self, env):
        html = tmpl(env, '{% from "components.html" import pagination %}{{ pagination(1, 3) }}')
        assert 'aria-label="Página 1"' in html
        assert 'Página siguiente' in html

class TestComponentIntegration:
    def test_multi_import(self, env):
        html = tmpl(env, '{% from "components.html" import sidebar_item, badge, status_badge, card %}{{ sidebar_item("/t", "h", "T") }}{{ badge("OK", "success") }}{{ status_badge("activo") }}{{ card("H", "B") }}')
        assert 'sidebar-item' in html
        assert 'badge-success' in html

class TestBaseTemplate:
    def test_has_design_system_css(self, env):
        tmpl = env.get_template('base.html')
        html = tmpl.render()
        for css in ['base.css','theme.css','layout.css','buttons.css','forms.css','tables.css','cards.css','badges.css','alerts.css','sidebar.css','dashboard.css','attendance.css','animations.css','utilities.css']:
            assert css in html, f'{css} not in base.html'

    def test_has_modular_js(self, env):
        tmpl = env.get_template('base.html')
        html = tmpl.render()
        for js in ['utils.js', 'theme.js', 'tables.js', 'modals.js', 'forms.js', 'dashboard.js', 'notifications.js', 'pwa.js']:
            assert js in html

    def test_no_old_css(self, env):
        tmpl = env.get_template('base.html')
        html = tmpl.render()
        assert 'lumini.css' not in html
        assert 'enhanced.css' not in html

class TestFilesExist:
    def test_all_js_files(self):
        js_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'js')
        for f in ['utils.js', 'theme.js', 'tables.js', 'modals.js', 'forms.js', 'dashboard.js', 'attendance.js', 'notifications.js', 'lumini.js', 'pwa.js', 'notification-manager.js']:
            assert os.path.exists(os.path.join(js_dir, f)), f"Missing: {f}"

    def test_all_css_files(self):
        css_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'css')
        for f in ['base.css', 'theme.css', 'layout.css', 'buttons.css', 'forms.css', 'tables.css', 'cards.css', 'badges.css', 'alerts.css', 'sidebar.css', 'dashboard.css', 'attendance.css', 'animations.css', 'utilities.css']:
            assert os.path.exists(os.path.join(css_dir, f)), f"Missing: {f}"

    def test_no_old_css_files(self):
        css_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'css')
        assert not os.path.exists(os.path.join(css_dir, 'lumini.css')), 'lumini.css should be removed'
        assert not os.path.exists(os.path.join(css_dir, 'enhanced.css')), 'enhanced.css should be removed'

    def test_all_component_templates(self):
        comp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates', 'components')
        for f in ['sidebar.html', 'card.html', 'table.html', 'modal.html', 'button.html', 'badge.html', 'alert.html', 'toast.html', 'empty_state.html', 'form.html', 'pagination.html', 'search.html']:
            assert os.path.exists(os.path.join(comp_dir, f)), f"Missing: {f}"
