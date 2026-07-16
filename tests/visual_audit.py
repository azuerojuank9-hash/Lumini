"""Visual quality audit: renders every page and checks HTML structure."""
import os, sys, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'
from flask_app import app, init_db, hash_pw
import sqlite3

TEST_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'colegios_db', 'testcolegio.db')
init_db('testcolegio')

def seed():
    conn = sqlite3.connect(TEST_DB); conn.row_factory = sqlite3.Row
    conn.execute("DELETE FROM rectores WHERE usuario='rector_prueba'")
    conn.execute("INSERT INTO rectores (id,nombre,usuario,password,email,activo,es_principal) VALUES (?,?,?,?,?,?,?)",
                 (99,'Rector Prueba','rector_prueba','ecd71870d1963316a97e3ac3408c9835ad8cf0f3c1bc703527c30265534f75ae','rector@test.com',1,1))
    conn.execute("INSERT OR IGNORE INTO directoras (nombre,usuario,password,email,activo,curso,jornada) VALUES (?,?,?,?,?,?,?)",
                 ('Directora','directora',hash_pw('test123'),'dir@test.com',1,'Primero A','Mañana'))
    conn.execute("INSERT OR IGNORE INTO profesores (id,nombre,usuario,password,email,activo) VALUES (?,?,?,?,?,?)",
                 (1,'Profesor','profesor1',hash_pw('test123'),'prof@test.com',1))
    conn.execute("INSERT OR IGNORE INTO alumnos (id,nombre,curso,jornada,activo) VALUES (?,?,?,?,?)",
                 (1,'Alumno','Primero A','Mañana',1))
    conn.execute("INSERT OR IGNORE INTO alumnos (id,nombre,curso,jornada,activo) VALUES (?,?,?,?,?)",
                 (2,'Alumno Dos','Primero A','Mañana',1))
    conn.execute('INSERT OR IGNORE INTO asignaciones_curso (profesor_id,materia,jornada,curso) VALUES (?,?,?,?)',
                 (1,'Matematicas','Mañana','Primero A'))
    conn.execute('INSERT OR IGNORE INTO asignaciones_curso (profesor_id,materia,jornada,curso) VALUES (?,?,?,?)',
                 (1,'Matematicas','Mañana','Segundo A'))
    conn.execute('INSERT OR IGNORE INTO actividades (id,profesor_id,materia,jornada,curso,nombre,orden,periodo) VALUES (?,?,?,?,?,?,?,?)',
                 (1,1,'Matematicas','Mañana','Primero A','Tarea 1',1,1))
    conn.commit(); conn.close()
seed()

app.config['TESTING'] = True
client = app.test_client()

def get_csrf():
    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'audit_csrf'
    return 'audit_csrf'

results = {
    'pages_reviewed': 0,
    'issues_found': [],
    'issues_fixed': [],
    'pages_ok': [],
    'pages_with_issues': []
}

def check(name, html, checks):
    """Run a list of checks on the HTML. Each check is (label, pass_fn) that returns True/False."""
    results['pages_reviewed'] += 1
    page_issues = []
    for label, fn in checks:
        try:
            if not fn(html):
                page_issues.append(label)
        except Exception as e:
            page_issues.append(f"{label} (ERROR: {e})")
    if page_issues:
        results['issues_found'].extend([f"{name}: {i}" for i in page_issues])
        results['pages_with_issues'].append(name)
    else:
        results['pages_ok'].append(name)

def has_viewport(html):
    return 'name="viewport"' in html or "name='viewport'" in html

def has_sidebar_block(html):
    return 'sidebar' in html.lower() and ('sidebar-nav' in html or 'sidebar-header' in html)

def has_no_hardcoded_colors(html):
    """Check for hardcoded colors that should use CSS vars."""
    # Skip known safe patterns (gradients using CSS vars, colors in data attrs, etc.)
    hardcoded = r'#[0-9a-fA-F]{3,6}|rgba?\([^)]+\)' 
    # Check lines that are style= or css blocks
    lines = html.split('\n')
    suspicious = []
    for i, line in enumerate(lines):
        # Skip lines with var()
        if 'var(' in line: continue
        # Skip commented-out CSS
        if line.strip().startswith('/*') or line.strip().startswith('*'): continue
        # Find color codes
        colors = re.findall(r'#[0-9a-fA-F]{6}\b', line)
        for c in colors:
            if c.upper() not in ['#FFFFFF','#000000','#FFF','#000']:
                suspicious.append(f"  L{i+1}: {c} in: {line.strip()[:120]}")
    if suspicious:
        # Don't fail, just report
        return True, suspicious
    return True, []

def has_lucide_icons(html):
    return 'data-lucide' in html or 'lucide' in html

def has_chart_js(html):
    return 'chart.js' in html or 'Chart' in html

def no_mojibake(html):
    """Check for replacement character / broken UTF-8"""
    return '\ufffd' not in html

def balanced_tags(html):
    """Check for balanced div tags (basic)"""
    opens = html.count('<div') 
    closes = html.count('</div>')
    return opens == closes

# ── Sessions ──
get_csrf()
# Admin login
client.post('/admin', data={'password':'admin123','_csrf_token':'audit_csrf'})
# Rector login
client.post('/testcolegio/rector/login', data={'usuario':'rector_prueba','password':'test123','_csrf_token':'audit_csrf'})
# Profesor login
client.post('/testcolegio/login', data={'usuario':'profesor1','password':'test123','_csrf_token':'audit_csrf'})
# Directora login
client.post('/testcolegio/directora/login', data={'usuario':'directora','password':'test123','_csrf_token':'audit_csrf'})

def render_and_check(name, url, checks, method='GET', data=None):
    if method == 'GET':
        resp = client.get(url)
    else:
        resp = client.post(url, data=data)
    html = resp.data.decode('utf-8', errors='replace')
    results['pages_reviewed'] += 1
    page_issues = []
    for label, fn in checks:
        try:
            result = fn(html)
            if isinstance(result, tuple):
                ok, extra = result
                if not ok:
                    page_issues.append(label)
                    if extra: 
                        for e in extra[:3]:
                            page_issues.append(f"  {e}")
            elif not result:
                page_issues.append(label)
        except Exception as e:
            page_issues.append(f"{label} (ERROR: {e})")
    if page_issues:
        results['issues_found'].extend(page_issues)
        results['pages_with_issues'].append((name, url))
    else:
        results['pages_ok'].append((name, url))
    return html

base_checks = [
    ('Viewport meta tag missing', lambda h: has_viewport(h)),
    ('Mojibake / broken UTF-8 chars', lambda h: no_mojibake(h)),
    ('Unbalanced <div> tags', lambda h: balanced_tags(h)),
]

sidebar_checks = base_checks + [
    ('No sidebar navigation found', lambda h: has_sidebar_block(h)),
]

login_checks = base_checks + [
    ('No sidebar should exist on login pages', lambda h: not has_sidebar_block(h)),
]

print("=" * 70)
print("VISUAL QUALITY AUDIT - Rendering every page...")
print("=" * 70)

# ── LANDING / LOGIN PAGES (should have NO sidebar) ──
print("\n--- LANDING / LOGIN PAGES ---")
render_and_check('Landing /', '/', login_checks)
render_and_check('Admin Login', '/admin', login_checks)
render_and_check('Rector Login', '/testcolegio/rector/login', login_checks)
render_and_check('Teacher Login', '/testcolegio/login', login_checks)
render_and_check('Directora Login', '/testcolegio/directora/login', login_checks)
render_and_check('Recuperar', '/testcolegio/recuperar', login_checks)

# ── ADMIN PAGES ──
print("\n--- ADMIN PAGES ---")
admin_checks = base_checks + [('No sidebar', lambda h: has_sidebar_block(h))]
render_and_check('Admin Panel', '/admin', admin_checks)
render_and_check('Admin Codigos', '/admin/codigos', admin_checks)
render_and_check('Admin Codigos testcolegio', '/admin/codigos/testcolegio', admin_checks)

# ── RECTOR PAGES ──
print("\n--- RECTOR PAGES ---")
rector_checks = base_checks + [('No sidebar', lambda h: has_sidebar_block(h))]
render_and_check('Rector Panel', '/testcolegio/rector', rector_checks)
render_and_check('Rector Profesores', '/testcolegio/rector/profesores', rector_checks)
render_and_check('Rector Estudiantes', '/testcolegio/rector/estudiantes', rector_checks)
render_and_check('Rector Cursos', '/testcolegio/rector/cursos', rector_checks)
render_and_check('Rector Horarios', '/testcolegio/rector/horarios', rector_checks)
render_and_check('Rector Reportes', '/testcolegio/rector/reportes', rector_checks)
render_and_check('Rector Configuracion', '/testcolegio/rector/configuracion', rector_checks)
render_and_check('Rector Asistencia', '/testcolegio/rector/asistencia', rector_checks)
render_and_check('Rector Solicitudes', '/testcolegio/rector/solicitudes', rector_checks)
render_and_check('Rector Auditoria', '/testcolegio/rector/auditoria', rector_checks)
render_and_check('Rector Comunicaciones', '/testcolegio/rector/comunicaciones', rector_checks)
render_and_check('Rector Canales', '/testcolegio/rector/canales', rector_checks)
render_and_check('Rector Gestion Rectores', '/testcolegio/rector/gestion-rectores', rector_checks)

# ── TEACHER PAGES ──
print("\n--- TEACHER PAGES ---")
teacher_checks = base_checks + [('No sidebar', lambda h: has_sidebar_block(h))]
render_and_check('Teacher Dashboard', '/testcolegio/dashboard', teacher_checks)
render_and_check('Teacher Notas (index)', '/testcolegio/', teacher_checks)
render_and_check('Teacher Asistencia', '/testcolegio/asistencia', teacher_checks)
render_and_check('Teacher Horarios', '/testcolegio/horarios', teacher_checks)
render_and_check('Teacher Importar Notas', '/testcolegio/importar_notas', teacher_checks)
render_and_check('Teacher Archivados', '/testcolegio/archivados', teacher_checks)
render_and_check('Teacher Transferir Curso', '/testcolegio/transferir_curso', teacher_checks)
render_and_check('Teacher Cambiar Password', '/testcolegio/cambiar_password', teacher_checks)
render_and_check('Teacher Seleccionar Jornada', '/testcolegio/seleccionar', teacher_checks)
render_and_check('Estudiante view', '/testcolegio/estudiante', teacher_checks)
render_and_check('Notificaciones', '/testcolegio/notificaciones', teacher_checks)

# ── DIRECTORA PAGES ──
print("\n--- DIRECTORA PAGES ---")
directora_checks = base_checks + [('No sidebar', lambda h: has_sidebar_block(h))]
render_and_check('Directora Panel', '/testcolegio/directora/panel', directora_checks)

# ── RECTOR ENTERPRISE PAGES ──
print("\n--- RECTOR ENTERPRISE PAGES ---")
render_and_check('Rector Expediente', '/testcolegio/rector/expediente', rector_checks)
render_and_check('Rector Observador', '/testcolegio/rector/observador', rector_checks)
render_and_check('Rector Certificados', '/testcolegio/rector/certificados', rector_checks)
render_and_check('Rector Calendario', '/testcolegio/rector/calendario', rector_checks)
render_and_check('Rector Mensajes', '/testcolegio/rector/mensajes', rector_checks)

# ── ERROR PAGES ──
print("\n--- ERROR PAGES ---")
render_and_check('404 Error', '/testcolegio/nonexistent', base_checks)

print("\n" + "=" * 70)
print("AUDIT COMPLETE")
print("=" * 70)
print(f"\nPages reviewed: {results['pages_reviewed']}")
print(f"Pages OK: {len(results['pages_ok'])}")
print(f"Pages with issues: {len(results['pages_with_issues'])}")
print(f"Issues found: {len(results['issues_found'])}")

if results['issues_found']:
    print("\n--- ISSUES ---")
    for issue in results['issues_found']:
        print(f"  ! {issue}")

# Save results
report = {
    'pages_reviewed': results['pages_reviewed'],
    'pages_ok': [str(p) for p in results['pages_ok']],
    'pages_with_issues': [str(p) for p in results['pages_with_issues']],
    'issues_found': results['issues_found'],
    'issues_count': len(results['issues_found'])
}
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'visual_audit_report.json'), 'w') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print(f"\nReport saved to tests/visual_audit_report.json")
