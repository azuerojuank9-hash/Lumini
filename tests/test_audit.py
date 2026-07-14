import os, sys, sqlite3, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'
from flask_app import app
import pytest

TEST_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'colegios_db', 'testcolegio.db')

def ensure_table():
    conn = sqlite3.connect(TEST_DB)
    conn.execute('''CREATE TABLE IF NOT EXISTS enterprise_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL,
        usuario_id INTEGER,
        usuario_tipo TEXT DEFAULT '',
        accion TEXT NOT NULL,
        categoria TEXT DEFAULT '',
        descripcion TEXT DEFAULT '',
        tabla TEXT DEFAULT '',
        registro_id INTEGER,
        valor_anterior TEXT,
        valor_nuevo TEXT,
        ip TEXT DEFAULT '',
        user_agent TEXT DEFAULT '',
        dispositivo TEXT DEFAULT '',
        navegador TEXT DEFAULT '',
        sesion_id TEXT DEFAULT '',
        nivel TEXT DEFAULT 'info',
        creado TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.commit()
    conn.close()

ensure_table()

@pytest.fixture
def conn():
    c = sqlite3.connect(TEST_DB)
    c.row_factory = sqlite3.Row
    yield c
    c.close()

def test_log_action(conn):
    from utils.audit_middleware import log_action
    lid = log_action(conn, 'testcolegio', 1, 'rector', 'login',
                     'Inicio de sesion', nivel='info')
    assert lid > 0
    row = conn.execute('SELECT * FROM enterprise_audit_log WHERE id=?', (lid,)).fetchone()
    assert row['accion'] == 'login'
    assert row['categoria'] == 'auth'

def test_log_action_with_table(conn):
    from utils.audit_middleware import log_action
    lid = log_action(conn, 'testcolegio', 1, 'teacher', 'grade_save',
                     'Nota guardada', tabla='notas', registro_id=42,
                     valor_anterior={}, valor_nuevo={'val': 4.5})
    row = conn.execute('SELECT * FROM enterprise_audit_log WHERE id=?', (lid,)).fetchone()
    assert row['tabla'] == 'notas'
    assert row['registro_id'] == 42
    assert row['categoria'] == 'academic'

def test_log_action_with_device_parsing(conn):
    from utils.audit_middleware import log_action
    ua = 'Mozilla/5.0 (Linux; Android 13) Chrome/120'
    lid = log_action(conn, 'testcolegio', 1, 'rector', 'login',
                     'Login desde movil', user_agent=ua)
    row = conn.execute('SELECT * FROM enterprise_audit_log WHERE id=?', (lid,)).fetchone()
    assert row['dispositivo'] == 'mobile'
    assert row['navegador'] == 'chrome'

def test_log_action_device_desktop(conn):
    from utils.audit_middleware import log_action
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/121'
    lid = log_action(conn, 'testcolegio', 1, 'rector', 'login',
                     'Login desktop', user_agent=ua)
    row = conn.execute('SELECT * FROM enterprise_audit_log WHERE id=?', (lid,)).fetchone()
    assert row['dispositivo'] == 'desktop'
    assert row['navegador'] == 'firefox'

def test_log_action_device_tablet(conn):
    from utils.audit_middleware import log_action
    ua = 'Mozilla/5.0 (iPad; CPU OS 17) AppleWebKit/605 Safari/604'
    lid = log_action(conn, 'testcolegio', 1, 'rector', 'login',
                     'Login tablet', user_agent=ua)
    row = conn.execute('SELECT * FROM enterprise_audit_log WHERE id=?', (lid,)).fetchone()
    assert row['dispositivo'] == 'tablet'

def test_log_action_browser_edge(conn):
    from utils.audit_middleware import log_action
    ua = 'Mozilla/5.0 (Windows NT 10.0) Chrome/120 Edg/120'
    lid = log_action(conn, 'testcolegio', 1, 'rector', 'export',
                     'Exportacion Excel', user_agent=ua)
    row = conn.execute('SELECT * FROM enterprise_audit_log WHERE id=?', (lid,)).fetchone()
    assert row['navegador'] == 'edge'

def test_query_audit_log(conn):
    from utils.audit_middleware import log_action, query_audit_log
    log_action(conn, 'testcol', 1, 'rector', 'login', 'Login 1')
    log_action(conn, 'testcol', 1, 'rector', 'logout', 'Logout 1')
    result = query_audit_log(conn, 'testcol')
    assert result['total'] >= 2
    assert len(result['data']) >= 2

def test_query_audit_log_filter_accion(conn):
    from utils.audit_middleware import log_action, query_audit_log
    log_action(conn, 'testcol', 1, 'rector', 'create', 'Crear prof')
    result = query_audit_log(conn, 'testcol', accion='create')
    assert result['total'] >= 1

def test_query_audit_log_filter_categoria(conn):
    from utils.audit_middleware import log_action, query_audit_log
    log_action(conn, 'qcol', 1, 'rector', 'pdf_download', 'PDF descargado')
    result = query_audit_log(conn, 'qcol', categoria='export')
    assert result['total'] >= 1

def test_query_audit_log_pagination(conn):
    from utils.audit_middleware import log_action, query_audit_log
    for i in range(3):
        log_action(conn, 'pcol', 1, 'rector', 'login', f'Login {i}')
    result = query_audit_log(conn, 'pcol', page=1, per_page=2)
    assert len(result['data']) <= 2
    assert result['page'] == 1
    assert result['per_page'] == 2
