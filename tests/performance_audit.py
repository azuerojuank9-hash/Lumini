"""Performance Audit — measure all key pages."""
import sys, os, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
os.environ['ENV'] = 'testing'

import flask_app as fa
fa.init_db('testcolegio')
app = fa.app

SLUG = 'testcolegio'

def measure(label, method, path, data=None, headers=None):
    with app.test_client() as c:
        start = time.perf_counter()
        if method == 'GET':
            resp = c.get(path, headers=headers or {})
        elif method == 'POST':
            resp = c.post(path, data=data, headers=headers or {})
        elapsed = (time.perf_counter() - start) * 1000
        status = resp.status_code
        slow = ' ** SLOW **' if elapsed > 500 else ''
        print(f'  {elapsed:7.1f}ms  [{status}] {method} {path}{slow}')
        return elapsed, status

print('='*70)
print('PERFORMANCE AUDIT — Lumini v2.1')
print('='*70)

results = []

results.append(('Login Rector GET', measure('Login Rector', 'GET', f'/{SLUG}/rector/login')))
results.append(('Login Directora GET', measure('Login Directora', 'GET', f'/{SLUG}/directora/login')))
results.append(('Login Teacher GET', measure('Login Teacher', 'GET', f'/{SLUG}/login')))

with app.test_client() as c:
    c.post(f'/{SLUG}/login', data={'usuario': 'profesor1', 'password': '123456', 'jornada': 'Mañana', 'accion': 'login'})
    results.append(('Teacher Dashboard', measure('Teacher Dashboard', 'GET', f'/{SLUG}/')))
    results.append(('Teacher Notas', measure('Teacher Notas', 'GET', f'/{SLUG}/notas')))
    results.append(('Teacher Asistencia', measure('Teacher Asistencia', 'GET', f'/{SLUG}/asistencia')))
    results.append(('Teacher Comunicaciones', measure('Teacher Comunicaciones', 'GET', f'/{SLUG}/comunicaciones')))
    results.append(('Teacher Plantilla Notas', measure('Teacher Plantilla', 'GET', f'/{SLUG}/notas/plantilla')))

with app.test_client() as c:
    c.post(f'/{SLUG}/rector/login', data={'usuario': 'admin', 'password': '12345678', 'accion': 'login'})
    results.append(('Rector Panel', measure('Rector Panel', 'GET', f'/{SLUG}/rector')))
    results.append(('Rector Profesores', measure('Rector Profesores', 'GET', f'/{SLUG}/rector/profesores')))
    results.append(('Rector Estudiantes', measure('Rector Estudiantes', 'GET', f'/{SLUG}/rector/estudiantes')))
    results.append(('Rector Configuracion', measure('Rector Config', 'GET', f'/{SLUG}/rector/configuracion')))
    results.append(('Rector Comunicaciones', measure('Rector Comunicaciones', 'GET', f'/{SLUG}/rector/comunicaciones')))
    results.append(('Rector Canales', measure('Rector Canales', 'GET', f'/{SLUG}/rector/canales')))

with app.test_client() as c:
    c.post(f'/{SLUG}/portal/login', json={'email': 'padre@test.com', 'pin': '1234'}, content_type='application/json')
    results.append(('Portal Padre Dashboard', measure('Parent Dashboard', 'GET', f'/{SLUG}/portal/dashboard')))

with app.test_client() as c:
    c.post(f'/{SLUG}/login', data={'nombre_est': 'alumno uno', 'jornada_est': 'Mañana', 'pin_est': '', 'accion': 'estudiante'})
    results.append(('Student Dashboard', measure('Student Dashboard', 'GET', f'/{SLUG}/estudiante')))

results.append(('Static CSS', measure('Static CSS', 'GET', '/static/css/base.css')))
results.append(('Static JS', measure('Static JS', 'GET', '/static/js/lumini.js')))

print()
print('='*70)
print('SUMMARY')
print('='*70)
total_ms = sum(r[0] for r in results)
print(f'  Total measured: {total_ms:.0f}ms across {len(results)} endpoints')
print(f'  Average: {total_ms/len(results):.1f}ms per endpoint')
slow = [(name, ms, status) for name, (ms, status) in results if ms > 500]
if slow:
    print(f'\n  SLOW ENDPOINTS (>{500}ms):')
    for name, ms, status in slow:
        print(f'    {ms:.0f}ms  [{status}] {name}')
else:
    print(f'\n  No slow endpoints (all < 500ms)')
print()
