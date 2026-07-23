"""Functional audit: visits every page for every role, checks HTTP 200, no 404/500."""
import json, os, re, sqlite3, sys, time, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'; os.environ['ENV'] = 'development'
from flask_app import app, hash_pw, init_db

TEST_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'colegios_db', 'testcolegio.db')

def seed():
    init_db('testcolegio')
    conn = sqlite3.connect(TEST_DB); conn.row_factory = sqlite3.Row
    conn.execute("DELETE FROM rectores WHERE usuario='rector_prueba'")
    conn.execute("INSERT INTO rectores (id,nombre,usuario,password,email,activo,es_principal) VALUES (?,?,?,?,?,?,?)",
                 (99,'Rector Prueba','rector_prueba','ecd71870d1963316a97e3ac3408c9835ad8cf0f3c1bc703527c30265534f75ae','rector@test.com',1,1))
    for tbl in ['directoras','profesores','alumnos','padres']:
        conn.execute(f"DELETE FROM {tbl}")
    conn.execute("INSERT INTO directoras (nombre,usuario,password,email,activo,curso,jornada) VALUES (?,?,?,?,?,?,?)",
                 ('Directora Prueba','directora',hash_pw('test123'),'dir@test.com',1,'Primero A','Mañana'))
    conn.execute("INSERT INTO profesores (id,nombre,usuario,password,email,activo) VALUES (?,?,?,?,?,?)",
                 (1,'Profesor Uno','profesor1',hash_pw('test123'),'prof@test.com',1))
    conn.execute("INSERT INTO alumnos (id,nombre,curso,jornada,activo) VALUES (?,?,?,?,?)",
                 (1,'Alumno Uno','Primero A','Mañana',1))
    conn.execute("INSERT INTO alumnos (id,nombre,curso,jornada,activo) VALUES (?,?,?,?,?)",
                 (2,'Alumno Dos','Primero A','Mañana',1))
    conn.execute("INSERT INTO alumnos (id,nombre,curso,jornada,activo) VALUES (?,?,?,?,?)",
                 (3,'Alumno Tres','Segundo A','Mañana',1))
    conn.execute('INSERT OR IGNORE INTO asignaciones_curso (profesor_id,materia,jornada,curso) VALUES (?,?,?,?)',
                 (1,'Matematicas','Mañana','Primero A'))
    conn.execute('INSERT OR IGNORE INTO asignaciones_curso (profesor_id,materia,jornada,curso) VALUES (?,?,?,?)',
                 (1,'Matematicas','Mañana','Segundo A'))
    conn.execute('INSERT OR REPLACE INTO periodos_estado (periodo,estado) VALUES (?,?)', (1,'abierto'))
    conn.execute('INSERT OR IGNORE INTO actividades (id,profesor_id,materia,jornada,curso,nombre,orden,periodo) VALUES (?,?,?,?,?,?,?,?)',
                 (1,1,'Matematicas','Mañana','Primero A','Tarea 1',1,1))
    conn.execute('INSERT OR IGNORE INTO padres (id,nombre,email,pin,activo) VALUES (?,?,?,?,?)',
                 (1,'Padre Uno','padre@test.com',hash_pw('1234'),1))
    try:
        conn.execute('INSERT OR IGNORE INTO alumno_padre (alumno_id,padre_id) VALUES (?,?)', (1,1))
    except sqlite3.OperationalError:
        pass
    conn.commit(); conn.close()
seed()
app.config['TESTING'] = True
client = app.test_client()
CSRF = 'audit_csrf_token'

def set_csrf():
    with client.session_transaction() as sess:
        sess['_csrf_token'] = CSRF

set_csrf()

results = {'ok': 0, 'redirect': 0, 'fail': 0, 'errors': []}
times = {}

def check(label, method, url, data=None, expect_redirect=False, session=None):
    start = time.time()
    try:
        if session:
            with client.session_transaction() as sess:
                for k, v in session.items():
                    sess[k] = v
                sess['_csrf_token'] = CSRF
        if method == 'GET':
            resp = client.get(url, follow_redirects=False)
        else:
            resp = client.post(url, data=data, follow_redirects=False)
        elapsed = round(time.time() - start, 3)
        times[label] = elapsed
        if resp.status_code in (301, 302):
            results['redirect'] += 1
            if expect_redirect:
                results['ok'] += 1
            else:
                results['fail'] += 1
                msg = f"[REDIRECT] {label}: {url} -> {resp.status_code} -> {resp.headers.get('Location','?')}"
                results['errors'].append(msg)
                print(f"  [REDIRECT] {msg}")
            return
        if resp.status_code == 200:
            results['ok'] += 1
            html = resp.data.decode('utf-8', errors='replace')
            # Check for common error patterns in the HTML
            checks = [
                ('Error interno del servidor', '500 in HTML'),
                ('Not Found', '404 in HTML'),
                ('Internal Server Error', '500 in HTML'),
                ('does not exist', 'missing resource'),
            ]
            for pattern, desc in checks:
                if pattern.lower() in html.lower():
                    results['fail'] += 1
                    results['errors'].append(f"[{desc}] {label}: {url}")
                    print(f"  [{desc}] {label}: {url}")
                    return
            # Check for broken resource references
            for attr, ext in [('href=', '.css'), ('src=', '.js'), ('src=', '.png'), ('src=', '.jpg'), ('src=', '.svg'), ('src=', '.webp'), ('href=', '.woff'), ('href=', '.ttf')]:
                for m in re.finditer(f'{attr}"([^"]+{ext})"', html, re.I):
                    rsrc = m.group(1)
                    if rsrc.startswith('http'):
                        continue
                    r = client.get(rsrc)
                    if r.status_code != 200:
                        results['fail'] += 1
                        results['errors'].append(f"[404 RESOURCE] {label}: {rsrc} ({r.status_code}) in {url}")
                        print(f"  [404 RESOURCE] {label}: {rsrc} ({r.status_code}) in {url}")
            return resp
        else:
            results['fail'] += 1
            results['errors'].append(f"[HTTP {resp.status_code}] {label}: {url}")
            print(f"  [HTTP {resp.status_code}] {label}: {url}")
    except Exception as e:
        results['fail'] += 1
        results['errors'].append(f"[EXCEPTION] {label}: {url} -> {e}")
        print(f"  [EXCEPTION] {label}: {url} -> {e}")

def check_get(label, url, expect_redirect=False, session=None):
    return check(label, 'GET', url, expect_redirect=expect_redirect, session=session)

def check_post(label, url, data, expect_redirect=False, session=None):
    return check(label, 'POST', url, data=data, expect_redirect=expect_redirect, session=session)

SLUG = 'testcolegio'

# ─────────────────────────────────────────────
print("=" * 70)
print("FUNCTIONAL AUDIT v2.1 — All Roles, All Pages")
print("=" * 70)

# ── 1. UNAUTHENTICATED PAGES ──
print("\n--- PUBLIC / LANDING PAGES ---")
check_get('Landing /', '/')
check_get('Offline', '/offline')
check_get('Login v2', f'/{SLUG}/login')
check_get('Recuperar', f'/{SLUG}/recuperar')
check_get('Rector Login', f'/{SLUG}/rector/login')
check_get('Rector Registrar', f'/{SLUG}/rector/registrar')
check_get('Directora Login', f'/{SLUG}/directora/login')
check_get('Directora Registrar', f'/{SLUG}/directora/registrar_directo')
check_get('Parent Login', f'/{SLUG}/portal/login')

# ── 2. ADMIN ──
print("\n--- ADMIN ---")
check_get('Admin Login', '/admin')
# Check admin pages before login (should redirect to login)
set_csrf()
check_get('Admin Codigos (no session)', '/admin/codigos', expect_redirect=True)
check_get('Admin Profesores (no session)', f'/admin/profesores/{SLUG}', expect_redirect=True)
# Login as admin
check_post('Admin Login POST', '/admin', data={'password': 'admin123', '_csrf_token': CSRF}, expect_redirect=True)
# Now check admin pages with session
set_csrf()
check_get('Admin Codigos', '/admin/codigos')
check_get('Admin Profesores', f'/admin/profesores/{SLUG}')
check_get('Admin Codigos Slug', f'/admin/codigos/{SLUG}')

# ── 3. RECTOR ──
print("\n--- RECTOR ---")
rector_sess = {'rector_id_testcolegio': 99}
# Check that rector pages redirect to login when not logged in
check_get('Rector Panel (no session)', f'/{SLUG}/rector/panel', expect_redirect=True)
check_get('Rector Profesores (no session)', f'/{SLUG}/rector/profesores', expect_redirect=True)

# Login as rector
set_csrf()
check_post('Rector Login POST', f'/{SLUG}/login', data={
    'accion': 'rector_login', 'rec_usuario': 'rector_prueba',
    'rec_password': 'test123', '_csrf_token': CSRF
}, expect_redirect=True)

# Rector pages
rector_pages = [
    ('Rector Panel', f'/{SLUG}/rector/panel'),
    ('Rector Profesores', f'/{SLUG}/rector/profesores'),
    ('Rector Estudiantes', f'/{SLUG}/rector/estudiantes'),
    ('Rector Cursos', f'/{SLUG}/rector/cursos'),
    ('Rector Reportes', f'/{SLUG}/rector/reportes'),
    ('Rector Asistencia', f'/{SLUG}/rector/asistencia'),
    ('Rector Configuracion', f'/{SLUG}/rector/configuracion'),
    ('Rector Solicitudes', f'/{SLUG}/rector/solicitudes'),
    ('Rector Auditoria', f'/{SLUG}/rector/auditoria'),
    ('Rector Comunicaciones', f'/{SLUG}/rector/comunicaciones'),
    ('Rector Canales', f'/{SLUG}/rector/canales'),
    ('Rector Gestion Rectores', f'/{SLUG}/rector/gestion-rectores'),
    ('Rector Horarios', f'/{SLUG}/rector/horarios'),
    ('Rector Expediente', f'/{SLUG}/rector/expediente'),
    ('Rector Observador', f'/{SLUG}/rector/observador'),
    ('Rector Certificados', f'/{SLUG}/rector/certificados'),
    ('Rector Calendario', f'/{SLUG}/rector/calendario'),
    ('Rector Mensajes', f'/{SLUG}/rector/mensajes'),
    ('Rector Comunicaciones Nueva', f'/{SLUG}/rector/comunicaciones/nueva'),
    ('Rector Canales Crear', f'/{SLUG}/rector/canales/crear'),
]
for label, url in rector_pages:
    check_get(label, url, session=rector_sess)

# ── 4. DIRECTORA ──
print("\n--- DIRECTORA ---")
set_csrf()
check_post('Directora Login POST', f'/{SLUG}/login', data={
    'accion': 'directora_login', 'dir_usuario': 'directora',
    'dir_password': 'test123', '_csrf_token': CSRF
}, expect_redirect=True)
directora_sess = {'directora_id_testcolegio': 1}
check_get('Directora Panel', f'/{SLUG}/directora/panel', session=directora_sess)

# ── 5. TEACHER ──
print("\n--- TEACHER ---")
set_csrf()
check_post('Teacher Login POST', f'/{SLUG}/login', data={
    'accion': 'profesor_login', 'usuario': 'profesor1',
    'password': 'test123', '_csrf_token': CSRF
}, expect_redirect=True)
teacher_sess = {
    'profesor_id_testcolegio': 1,
    'rol_testcolegio': 'profesor',
    'jornada_testcolegio': 'Mañana',
    'materia_testcolegio': 'Matematicas',
}
teacher_pages = [
    ('Teacher Dashboard', f'/{SLUG}/dashboard'),
    ('Teacher Home', f'/{SLUG}/home'),
    ('Teacher Actividades List', f'/{SLUG}/actividades/list'),
    ('Teacher Actividades Crear', f'/{SLUG}/actividades/crear'),
    ('Teacher Notas Batch', f'/{SLUG}/notas/batch'),
    ('Teacher Notas Pagina', f'/{SLUG}/notas/pagina'),
    ('Teacher Importar Notas', f'/{SLUG}/importar_notas'),
    ('Teacher Asistencia', f'/{SLUG}/asistencia'),
    ('Teacher Archivados', f'/{SLUG}/archivados'),
    ('Teacher Horarios', f'/{SLUG}/horarios'),
    ('Teacher Calendario', f'/{SLUG}/calendario'),
    ('Teacher Comunicados', f'/{SLUG}/comunicados'),
    ('Teacher Plantillas', f'/{SLUG}/plantillas'),
    ('Teacher Config', f'/{SLUG}/config'),
    ('Teacher Auditoria', f'/{SLUG}/auditoria'),
    ('Teacher Sugerencias', f'/{SLUG}/sugerencias'),
    ('Teacher Comparar', f'/{SLUG}/comparar'),
    ('Teacher Timeline', f'/{SLUG}/timeline'),
    ('Teacher Smart Hub', f'/{SLUG}/smart-hub'),
    ('Teacher Alertas', f'/{SLUG}/alertas'),
    ('Teacher Curso Analitica', f'/{SLUG}/curso/analitica'),
    ('Teacher Curso Ranking', f'/{SLUG}/curso/ranking'),
    ('Teacher Validar', f'/{SLUG}/validar'),
    ('Teacher Historial Curso', f'/{SLUG}/historial_curso'),
    ('Teacher Institut Dashboard', f'/{SLUG}/institucional/dashboard'),
    ('Teacher Institut Centro Control', f'/{SLUG}/institucional/centro-control'),
    ('Teacher Plantilla Notas', f'/{SLUG}/plantilla_notas'),
    ('Teacher Exportar Notas', f'/{SLUG}/exportar_notas'),
    ('Teacher Cambiar Password', f'/{SLUG}/cambiar_password'),
    ('Teacher Actividad 1', f'/{SLUG}/actividades/1'),
    ('Teacher Estudiante 1 Expediente', f'/{SLUG}/estudiante/1/expediente'),
    ('Teacher Notificaciones', f'/{SLUG}/notificaciones'),
    ('Teacher Centro Control', f'/{SLUG}/institucional/centro-control'),
]
for label, url in teacher_pages:
    check_get(label, url, session=teacher_sess)

# ── 6. STUDENT ──
print("\n--- STUDENT ---")
set_csrf()
check_post('Student Login POST', f'/{SLUG}/login', data={
    'accion': 'estudiante', 'nombre_est': 'Alumno Uno',
    'jornada_est': 'Mañana', 'pin_est': '', '_csrf_token': CSRF
}, expect_redirect=True)
student_sess = {
    'alumno_id_testcolegio': 1,
    'alumno_nombre_testcolegio': 'Alumno Uno',
    'alumno_curso_testcolegio': 'Primero A',
    'alumno_jornada_testcolegio': 'Mañana',
}
check_get('Student Dashboard', f'/{SLUG}/estudiante', session=student_sess)

# ── 7. PARENT ──
print("\n--- PARENT ---")
set_csrf()
parent_sess = {'padre_id_testcolegio': 1}
parent_pages = [
    ('Parent Dashboard', f'/{SLUG}/portal/dashboard'),
    ('Parent Notas', f'/{SLUG}/portal/notas/1'),
    ('Parent Asistencia', f'/{SLUG}/portal/asistencia/1'),
    ('Parent Comunicados', f'/{SLUG}/portal/comunicados'),
]
for label, url in parent_pages:
    check_get(label, url, session=parent_sess)

# ── 8. STATIC ASSETS ──
print("\n--- STATIC ASSETS ---")
css_files = ['base.css','theme.css','layout.css','buttons.css','forms.css','tables.css',
             'cards.css','badges.css','alerts.css','sidebar.css','dashboard.css',
             'attendance.css','animations.css','utilities.css']
for f in css_files:
    check_get(f'CSS {f}', f'/static/css/{f}')

js_files = ['utils.js','theme.js','tables.js','modals.js','forms.js','dashboard.js',
            'notifications.js','pwa.js','lumini.js','attendance.js','notification-manager.js']
for f in js_files:
    check_get(f'JS {f}', f'/static/js/{f}')

check_get('Favicon', '/static/lumini_logo.webp')
check_get('Manifest', '/static/manifest.json')

# ── SUMMARY ──
print("\n" + "=" * 70)
print("AUDIT RESULTS")
print("=" * 70)
print(f"  OK (200):       {results['ok']}")
print(f"  Redirect:       {results['redirect']}")
print(f"  Failures:       {results['fail']}")
print(f"  Total pages:    {results['ok'] + results['redirect'] + results['fail']}")
if times:
    slow = sorted(times.items(), key=lambda x: -x[1])[:5]
    print(f"\n  Slowest pages:")
    for label, sec in slow:
        print(f"     {sec:.3f}s  {label}")
print(f"\n  Errors ({len(results['errors'])}):")
for e in results['errors']:
    print(f"    {e}")

# Write JSON report
report = {
    'ok': results['ok'],
    'redirect': results['redirect'],
    'fail': results['fail'],
    'total_pages': results['ok'] + results['redirect'] + results['fail'],
    'errors': results['errors'],
}
report_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'audit_report.json')
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\n  Report saved: {report_path}")

if results['fail'] > 0:
    print("\n  AUDIT FAILED -- fix errors above and re-run")
    exit(1)
else:
    print("\n  AUDIT PASSED -- all pages return 200 with clean HTML")
    exit(0)
