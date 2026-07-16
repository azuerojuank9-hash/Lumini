"""Final visual audit with isolated sessions."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'
from flask_app import app, hash_pw, init_db
import sqlite3

TEST_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'colegios_db', 'testcolegio.db')
init_db('testcolegio')
conn = sqlite3.connect(TEST_DB)
conn.execute("DELETE FROM rectores WHERE usuario='rector_prueba'")
conn.execute("INSERT OR IGNORE INTO rectores (id,nombre,usuario,password,email,activo,es_principal) VALUES (?,?,?,?,?,?,?)",
             (99,'Rector Prueba','rector_prueba','ecd71870d1963316a97e3ac3408c9835ad8cf0f3c1bc703527c30265534f75ae','rector@test.com',1,1))
conn.execute("INSERT OR IGNORE INTO profesores (id,nombre,usuario,password,email,activo) VALUES (?,?,?,?,?,?)",
             (1,'Profesor','profesor1',hash_pw('test123'),'prof@test.com',1))
conn.execute("INSERT OR IGNORE INTO alumnos (id,nombre,curso,jornada,activo) VALUES (?,?,?,?,?)",
             (1,'Alumno','Primero A','Mañana',1))
conn.execute("INSERT OR IGNORE INTO alumnos (id,nombre,curso,jornada,activo) VALUES (?,?,?,?,?)",
             (2,'Alumno Dos','Primero A','Mañana',1))
conn.execute("INSERT OR IGNORE INTO directoras (nombre,usuario,password,email,activo,curso,jornada) VALUES (?,?,?,?,?,?,?)",
             ('Directora','directora',hash_pw('test123'),'dir@test.com',1,'Primero A','Mañana'))
conn.execute('INSERT OR IGNORE INTO asignaciones_curso (profesor_id,materia,jornada,curso) VALUES (?,?,?,?)',
             (1,'Matematicas','Mañana','Primero A'))
conn.execute('INSERT OR IGNORE INTO asignaciones_curso (profesor_id,materia,jornada,curso) VALUES (?,?,?,?)',
             (1,'Matematicas','Mañana','Segundo A'))
conn.execute('INSERT OR IGNORE INTO actividades (id,profesor_id,materia,jornada,curso,nombre,orden,periodo) VALUES (?,?,?,?,?,?,?,?)',
             (1,1,'Matematicas','Mañana','Primero A','Tarea 1',1,1))
conn.commit(); conn.close()

app.config['TESTING'] = True

all_results = {'ok': [], 'issues': []}

def check(name, url, session_kv):
    """Create FRESH client and test one page."""
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess.clear()
            sess['_csrf_token'] = 'test'
            for k, v in session_kv.items():
                sess[k] = v
        resp = client.get(url, follow_redirects=True)
        html = resp.data.decode('utf-8', errors='replace')
    
    has_sidebar = ('sidebar-nav' in html) or ('sidebar-item' in html) or ('class="sidebar"' in html) or ('sidebar-link' in html)
    has_vp = 'name="viewport"' in html
    is_login = 'Ingresa tu usuario' in html or 'login-wrap' in html
    bad_utf8 = '\ufffd' in html
    
    issues = []
    if not has_vp: issues.append('NO-VIEWPORT')
    if is_login: issues.append('LOGIN-PAGE')
    if bad_utf8: issues.append('BAD-UTF8')
    if not has_sidebar and not is_login: issues.append('NO-SIDEBAR')
    
    tag = ','.join(issues) if issues else 'OK'
    if tag == 'OK':
        all_results['ok'].append(name)
        print(f"  [OK] {name:40s} {url}")
    else:
        all_results['issues'].append((name, issues))
        print(f"  [{' '.join(issues):20s}] {name:40s} {url}")
    return issues

print("=" * 75)
print("FINAL VISUAL AUDIT - Isolated sessions")
print("=" * 75)

print("\n--- LANDING ---")
check('Landing', '/', {})

print("\n--- ADMIN (session: admin_auth) ---")
for n, u in [('Panel','/admin'),('Codigos','/admin/codigos'),('Codigos/testcolegio','/admin/codigos/testcolegio')]:
    check(f'Admin {n}', u, {'admin_auth': True})

print("\n--- RECTOR (session: rector_id_testcolegio=99) ---")
for n, u in [
    ('Panel','/testcolegio/rector'),('Profesores','/testcolegio/rector/profesores'),
    ('Estudiantes','/testcolegio/rector/estudiantes'),('Cursos','/testcolegio/rector/cursos'),
    ('R. Horarios','/testcolegio/rector/horarios'),('Reportes','/testcolegio/rector/reportes'),
    ('Config','/testcolegio/rector/configuracion'),('R. Asistencia','/testcolegio/rector/asistencia'),
    ('Solicitudes','/testcolegio/rector/solicitudes'),('Auditoria','/testcolegio/rector/auditoria'),
    ('Comunicaciones','/testcolegio/rector/comunicaciones'),('Canales','/testcolegio/rector/canales'),
    ('Expediente','/testcolegio/rector/expediente'),('Observador','/testcolegio/rector/observador'),
    ('Certificados','/testcolegio/rector/certificados'),('Calendario','/testcolegio/rector/calendario'),
    ('Mensajes','/testcolegio/rector/mensajes'),
]:
    check(f'Rector {n}', u, {'rector_id_testcolegio': 99})

print("\n--- TEACHER (session: profesor_id_testcolegio=1, jornada, materia) ---")
for n, u in [
    ('Notas (index)','/testcolegio/'),('Dashboard','/testcolegio/dashboard'),
    ('Asistencia','/testcolegio/asistencia'),('Horarios','/testcolegio/horarios'),
    ('Archivados','/testcolegio/archivados'),('Cambiar PW','/testcolegio/cambiar_password'),
    ('Importar','/testcolegio/importar_notas'),('Transferir','/testcolegio/transferir_curso'),
    ('Notificaciones','/testcolegio/notificaciones'),('Seleccionar','/testcolegio/seleccionar'),
    ('Estudiante','/testcolegio/estudiante'),
]:
    check(f'Teacher {n}', u, {
        'profesor_id_testcolegio': 1, 'rol_testcolegio': 'profesor',
        'jornada_testcolegio': 'Mañana', 'materia_testcolegio': 'Matematicas'
    })

print("\n--- DIRECTORA (session: directora_id_testcolegio=1) ---")
check('Directora Panel', '/testcolegio/directora/panel', {'directora_id_testcolegio': 1})

print("\n" + "=" * 75)
print(f"TOTAL PAGES CHECKED: {len(all_results['ok']) + len(all_results['issues'])}")
print(f"OK: {len(all_results['ok'])}")
print(f"WITH ISSUES: {len(all_results['issues'])}")
if all_results['issues']:
    print(f"\nISSUES:")
    for name, issues in all_results['issues']:
        print(f"  {name}: {', '.join(issues)}")
print("=" * 75)
