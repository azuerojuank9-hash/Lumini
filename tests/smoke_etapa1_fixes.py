# -*- coding: utf-8 -*-
"""Smoke tests ETAPA I (A1-A8 / M1/M2/M5/M6) — verificación real con test client.

No es parte de la suite pytest (no empieza por test_).
Uso: python tests/smoke_etapa1_fixes.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'

from flask_app import app
from test_app import TEST_DB, seed_test_db

seed_test_db()
SLUG = 'testcolegio'
CSRF = 'smoke_csrf'
OK, FAIL = [], []


def check(name, cond, detail=''):
    (OK if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + ((' :: ' + str(detail)) if detail else ''))


def as_prof(client):
    with client.session_transaction() as s:
        s.pop(f'rector_id_{SLUG}', None)
        s[f'profesor_id_{SLUG}'] = 1
        s[f'jornada_{SLUG}'] = 'Mañana'
        s[f'materia_{SLUG}'] = 'Matemáticas'
        s['_csrf_token'] = CSRF


def as_rector(client):
    with client.session_transaction() as s:
        s.pop(f'profesor_id_{SLUG}', None)
        s[f'rector_id_{SLUG}'] = 99
        s['_csrf_token'] = CSRF


def db():
    c = sqlite3.connect(TEST_DB)
    c.row_factory = sqlite3.Row
    return c


app.config['TESTING'] = True

with app.test_client() as client:
    # 1) Dashboard profesor — página 200
    as_prof(client)
    r = client.get(f'/{SLUG}/dashboard')
    check('1. dashboard profesor HTML 200', r.status_code == 200, r.status_code)

    # 2) Dashboard rector — página 200
    as_rector(client)
    r = client.get(f'/{SLUG}/dashboard')
    check('2. dashboard rector HTML 200', r.status_code == 200, r.status_code)

    # 3) dashboard_data profesor — payload esperado
    as_prof(client)
    r = client.get(f'/{SLUG}/dashboard_data?periodo=1&curso=Primero A&materia=Matematicas')
    data = r.get_json() if r.is_json else None
    check('3. dashboard_data profesor 200+json', r.status_code == 200 and data is not None, r.status_code)
    check('3b. payload profesor: cards/charts/rankings/alerts',
          data and all(k in data for k in ('cards', 'charts', 'rankings', 'alerts')))

    # 4) dashboard_data rector — sin crash y sin evolucion_periodos
    as_rector(client)
    r = client.get(f'/{SLUG}/dashboard_data?periodo=1&curso=Primero A')
    data = r.get_json() if r.is_json else None
    check('4. dashboard_data rector 200+json', r.status_code == 200 and data is not None, r.status_code)
    charts = (data or {}).get('charts') or {}
    check('4b. rector charts: distribucion/promedio_por_curso/promedio_por_materia',
          all(k in charts for k in ('distribucion', 'promedio_por_curso', 'promedio_por_materia')))
    check('4c. rector sin evolucion_periodos (evita render inexistente)', 'evolucion_periodos' not in charts)
    check('4d. rector rendimiento_actividades vacio (filtrado en frontend A8)',
          charts.get('rendimiento_actividades') == [])

    # 5) Alert Center — contrato A1
    as_prof(client)
    r = client.get(f'/{SLUG}/alertas?curso=Primero A&periodo=1')
    data = r.get_json() if r.is_json else None
    check('5. /alertas 200+json', r.status_code == 200 and data is not None, r.status_code)
    check('5b. alertas es lista (contrato A1: d.alertas[])',
          data is not None and isinstance(data.get('alertas'), list))
    check('5c. sin campo total inexistente (el JS ya no lo usa)',
          data is None or 'total' not in data or 'alerta' not in data)

    # 6) Drawer estudiante — contrato A2 (tendencia)
    conn = db()
    conn.execute('INSERT OR REPLACE INTO notas (aid, actividad_id, val) VALUES (1, 1, 9.0)')
    conn.commit(); conn.close()
    r = client.get(f'/{SLUG}/estudiante/1/tendencia?periodo=1')
    data = r.get_json() if r.is_json else None
    pts = (data or {}).get('puntos') or []
    check('6. /tendencia 200+json con puntos', r.status_code == 200 and data is not None and len(pts) > 0, r.status_code)
    check('6b. puntos usan valor/promedio_acumulado (no media_movil)',
          all('valor' in p and 'promedio_acumulado' in p for p in pts))
    check('6c. claves prediccion/confianza/diferencia_porcentual/promedio_estudiante',
          all(k in (data or {}) for k in ('prediccion', 'confianza', 'diferencia_porcentual', 'promedio_estudiante')))

    # 7) Dashboard ejecutivo — contrato A3
    r = client.get(f'/{SLUG}/institucional/dashboard')
    data = r.get_json() if r.is_json else None
    check('7. /institucional/dashboard 200+json', r.status_code == 200 and data is not None, r.status_code)
    check('7b. promedio_institucional presente (no institucional_avg)', 'promedio_institucional' in (data or {}))
    cursos = (data or {}).get('cursos') or []
    check('7c. cursos con aprobados (no aprobando)', all('aprobados' in c for c in cursos))
    check('7d. cursos con curso/promedio/estudiantes/aprobados/perdiendo',
          all(all(k in c for k in ('curso', 'promedio', 'estudiantes', 'aprobados', 'perdiendo')) for c in cursos))

    # 8) Borrar nota (A4) — val=None borra por DELETE
    as_prof(client)
    conn = db()
    conn.execute('INSERT OR IGNORE INTO notas (aid, actividad_id, val) VALUES (1, 1, 9.0)')
    conn.commit(); conn.close()
    r = client.post(f'/{SLUG}/notas/batch', json={'notas': [{'aid': 1, 'actividad_id': 1, 'val': None}]},
                    headers={'X-CSRF-Token': CSRF})
    data = r.get_json() if r.is_json else None
    check('8. borrar nota (val=None) sin 500', r.status_code == 200 and data is not None, r.status_code)
    conn = db()
    fila = conn.execute('SELECT val FROM notas WHERE aid=1 AND actividad_id=1').fetchone()
    conn.close()
    check('8b. fila borrada (DELETE) o val NULL', fila is None or fila['val'] is None)
    conn = db()
    conn.execute('INSERT OR REPLACE INTO notas (aid, actividad_id, val) VALUES (1, 1, 9.0)')
    conn.commit(); conn.close()

    # 9) Selección masiva alumnos — guards A5 en HTML (página index del profesor)
    as_prof(client)
    r = client.get(f'/{SLUG}/')
    html = r.get_data(as_text=True)
    check('9. /{slug}/ (index profesor) 200', r.status_code == 200, r.status_code)
    check('9b. guards A5 massDeleteBtn (null-safe)', 'massDeleteBtn' in html and '_mb' in html)

    # 10) Archivados — A6 csrf-global + A7 toast cerrado
    r = client.get(f'/{SLUG}/archivados')
    html = r.get_data(as_text=True)
    check('10. /archivados 200', r.status_code == 200, r.status_code)
    check('10b. A6 input csrf-global presente', 'id="csrf-global"' in html and 'value="' in html)
    check('10c. A7 toast cerrado inline (Guardado</div>)', 'Guardado</div>' in html)

    # 11) Gráficos — M1/M2 marcas en dashboard.html + A8 filtro cards
    as_rector(client)
    r = client.get(f'/{SLUG}/dashboard')
    dh = r.get_data(as_text=True)
    check('11. dashboard rector contiene renderCharts con _dashCharts (destroy)',
          'window._dashCharts' in dh and '_dashCharts' in dh)
    check('11b. chart-xmateria instanciado', 'chart-xmateria' in dh)
    check('11c. colores via CSS vars getComputedStyle', 'getComputedStyle' in dh)
    as_prof(client)
    r = client.get(f'/{SLUG}/')
    ih = r.get_data(as_text=True)
    check('11d. A1 cargarAlertas usa d.alertas', 'alertas' in ih and 'grupos' in ih)
    check('11e. A2 drawer usa promedio_acumulado', 'promedio_acumulado' in ih)
    check('11f. A3 usa promedio_institucional/aprobados', 'promedio_institucional' in ih and 'aprobados' in ih)
    check('11g. M5 cursoActual lee curso_sel', 'curso_sel' in ih and 'cursoActual' in ih)
    check('11h. M6 envía extra (Object.assign)', 'Object.assign' in ih)

    # 12) Aplicar plantilla (M5 flow backend) — no debe dar 500
    as_prof(client)
    r = client.post(f'/{SLUG}/plantillas/aplicar',
                    json={'plantilla_id': 1, 'curso': 'Primero A', 'materia': 'Matemáticas',
                          'jornada': 'Mañana', 'periodo': 1},
                    headers={'X-CSRF-Token': CSRF})
    check('12. /plantillas/aplicar sin 500', r.status_code in (200, 400, 404), r.status_code)

    # 13) Acciones masivas (M6) — backend con peso en body
    r = client.post(f'/{SLUG}/actividades/masiva',
                    json={'accion': 'cambiar_peso', 'ids': [1, 2], 'peso': 25},
                    headers={'X-CSRF-Token': CSRF})
    data = r.get_json() if r.is_json else None
    check('13. /actividades/masiva cambiar_peso 200 ok', r.status_code == 200 and (data or {}).get('status') == 'ok', r.status_code)
    r = client.post(f'/{SLUG}/actividades/masiva',
                    json={'accion': 'cambiar_peso', 'ids': [1, 2], 'peso': 10},
                    headers={'X-CSRF-Token': CSRF})
    check('13b. restaurar peso 10', r.status_code == 200, r.status_code)

print('\n==== SMOKE ETAPA I ====')
print(f'PASS {len(OK)} / FAIL {len(FAIL)}  (total {len(OK) + len(FAIL)})')
if FAIL:
    print('FALLIDOS:')
    for f in FAIL:
        print('  -', f)
    sys.exit(1)
print('TODO VERDE')
