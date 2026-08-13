"""Benchmark FASE 3 — guardado de notas antes/despues.

Compara el flujo anterior (una peticion por nota + un /recalcular por alumno)
contra el flujo nuevo (un unico POST /notas/batch que devuelve los calculos).

Uso (no lo recoge pytest por nombre):
    python tests/bench_notas.py
"""

import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'

from flask_app import app
from test_app import TEST_DB, seed_test_db

seed_test_db()

SLUG = 'testcolegio'
CSRF = 'bench_csrf'
S = 30  # alumnos/notas por lote


def db():
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    return conn


def preparar():
    conn = db()
    conn.execute('INSERT OR REPLACE INTO periodos_estado (periodo, estado) VALUES (?, ?)', (1, 'abierto'))
    # Limpiar notas/auditoria para una medicion limpia
    conn.execute('DELETE FROM auditoria_notas')
    conn.execute('DELETE FROM notas')
    # N alumnos de prueba
    conn.execute("DELETE FROM alumnos WHERE nombre LIKE 'Bench %'")
    aids = []
    for i in range(S):
        cur = conn.execute("INSERT INTO alumnos (nombre, curso, jornada, activo) VALUES (?,?,?,1)",
                           (f'Bench {i}', 'Primero A', 'Mañana'))
        aids.append(cur.lastrowid)
    conn.commit()
    conn.close()
    return aids


def teacher():
    app.config['TESTING'] = True
    return app.test_client()


def main():
    aids = preparar()
    c = teacher()
    with c.session_transaction() as sess:
        sess[f'profesor_id_{SLUG}'] = 1
        sess[f'rol_{SLUG}'] = 'profesor'
        sess[f'jornada_{SLUG}'] = 'Mañana'
        sess[f'materia_{SLUG}'] = 'Matemáticas'
        sess['_csrf_token'] = CSRF

    # ── NUEVO flujo: 1 POST /notas/batch (sin recalcular) ──
    notas = [{'aid': a, 'actividad_id': 1, 'val': round(3.0 + (i % 20) / 10, 1)} for i, a in enumerate(aids)]
    t0 = time.perf_counter()
    r = c.post(f'/{SLUG}/notas/batch', json={'notas': notas}, headers={'X-CSRF-Token': CSRF})
    t_new = time.perf_counter() - t0
    body = r.get_json()
    assert r.status_code == 200 and body.get('status') == 'ok'
    assert len(body.get('calculos', {})) == S, f'calculos incompletos: {len(body.get("calculos", {}))}'

    # ── VIEJO flujo: S × POST /guardar_nota + S × GET /recalcular ──
    t0 = time.perf_counter()
    for i, a in enumerate(aids):
        r1 = c.post(f'/{SLUG}/guardar_nota', data={
            'actividad_id': 1, 'aid': a, 'val': str(round(3.0 + (i % 20) / 10, 1)), '_csrf_token': CSRF})
        assert r1.status_code == 200
        r2 = c.get(f'/{SLUG}/recalcular/{a}')
        assert r2.status_code == 200
    t_old = time.perf_counter() - t0

    mejora = (1 - t_new / t_old) * 100 if t_old else 0
    print(f'NOTAS EN LOTE: {S}')
    print(f'  NUEVO (1x /notas/batch)   : {t_new * 1000:8.1f} ms  ({t_new:.2f} s)')
    print(f'  VIEJO (Sx /guardar_nota + recalcular): {t_old * 1000:8.1f} ms  ({t_old:.2f} s)')
    print(f'  MEJORA: {mejora:.1f}%')


if __name__ == '__main__':
    main()
