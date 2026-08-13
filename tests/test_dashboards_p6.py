"""P6 — Role dashboards show real data only.

Asserts the P6 dashboard work:
  - Rector panel: no fabricated trends, real KPIs (solicitudes pendientes,
    promedio institucional, bajo rendimiento, estado del período) and charts
    fed with real query results.
  - Student dashboard: shows período actual, materias, inasistencias and
    próximas evaluaciones from real data.
  - Parent portal: new Horario/Observaciones/Historial endpoints are guarded
    by the child-relationship check (403 for unlinked children) and return
    real data; comunicados carry fecha_creacion.
  - Directora panel: KPI row with real indicators per período.
"""

import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'

import pytest

from flask_app import app
from test_app import TEST_DB, seed_test_db

seed_test_db()

SLUG = 'testcolegio'
CSRF = 'p6_dashboard_csrf'


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


def db():
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    return conn


def seed_p6_parent():
    conn = db()
    conn.execute('INSERT OR IGNORE INTO padres (id, nombre, email, pin, activo) VALUES (?,?,?,?,?)',
                 (101, 'Padre P6', 'padre_p6@test.com', '4321', 1))
    hijo = conn.execute("SELECT id, nombre FROM alumnos WHERE nombre='Alumno Uno' ORDER BY id LIMIT 1").fetchone()
    if hijo:
        conn.execute('INSERT OR IGNORE INTO alumno_padre (padre_id, alumno_id) VALUES (?,?)', (101, hijo['id']))
    conn.commit()
    conn.close()
    return hijo


# ── RECTOR ────────────────────────────────────────────────────────────────

class TestRectorDashboard:
    def _rector_session(self, client):
        with client.session_transaction() as sess:
            sess[f'rector_id_{SLUG}'] = 99
            sess['_csrf_token'] = CSRF

    def test_rector_panel_has_no_fabricated_data(self, client, csrf):
        self._rector_session(client)
        r = client.get(f'/{SLUG}/rector/panel')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'vs mes ant' not in html
        assert 'Cobertura' not in html
        assert 'Ocupaci\u00f3n' not in html

    def test_rector_panel_real_kpis(self, client, csrf):
        # Seed a real pending solicitud for this colegio and read the real
        # counts straight from the DB the panel queries.
        conn = db()
        prof = conn.execute("SELECT id FROM profesores WHERE nombre='Profesor Uno'").fetchone()
        alum = conn.execute("SELECT id FROM alumnos ORDER BY id LIMIT 1").fetchone()
        prof_id = prof['id'] if prof else 1
        aid = alum['id'] if alum else 1
        conn.execute(
            '''INSERT INTO solicitudes_modificacion
               (slug, aid, profesor_id, materia, curso, jornada, periodo, tipo,
                actividad_id, valor_actual, valor_solicitado, motivo, estado)
               VALUES (?,?,?,?,?,?,?,?,NULL,'4.0','4.5','P6 test','pendiente')''',
            (SLUG, aid, prof_id, 'Matemáticas', 'Primero A', 'Mañana', 1, 'actividad'))
        conn.commit()
        pend_count = conn.execute(
            "SELECT COUNT(*) as c FROM solicitudes_modificacion WHERE estado='pendiente' AND slug=?",
            (SLUG,)).fetchone()['c']
        # M4: the rector panel shows the same weighted 65/25/10 institutional
        # average as the dashboard, so compute the expected value that way.
        from app.infra.grades import _promedio_ponderado
        notas_rows = conn.execute(
            'SELECT n.aid, n.val, ac.materia, ac.jornada '
            'FROM notas n JOIN actividades ac ON ac.id=n.actividad_id').fetchall()
        ev_rows = conn.execute(
            'SELECT aid, materia, jornada, evaluacion, autoevaluacion FROM evaluaciones').fetchall()
        notas_idx = {}
        for r in notas_rows:
            notas_idx.setdefault((r['aid'], r['materia'], r['jornada']), []).append(r['val'])
        ev_idx = {}
        for r in ev_rows:
            ev_idx[(r['aid'], r['materia'], r['jornada'])] = r
        subj_final = {}
        for key in set(notas_idx) | set(ev_idx):
            ev = ev_idx.get(key)
            ev_v = ev['evaluacion'] if ev and ev['evaluacion'] is not None else None
            au_v = ev['autoevaluacion'] if ev and ev['autoevaluacion'] is not None else None
            final = _promedio_ponderado(notas_idx.get(key, []), ev_v, au_v)
            if final is not None:
                subj_final[key] = final
        overall = {}
        for (aid, _m, _j), final in subj_final.items():
            overall.setdefault(aid, []).append(final)
        overall = {aid: sum(v) / len(v) for aid, v in overall.items()}
        prom_val = round(sum(overall.values()) / len(overall), 2) if overall else None
        conn.close()

        self._rector_session(client)
        r = client.get(f'/{SLUG}/rector/panel')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'Solicitudes pendientes' in html
        assert str(pend_count) in html
        assert 'Promedio institucional' in html
        if prom_val is not None:
            assert str(prom_val) in html
        assert 'Bajo rendimiento' in html
        assert 'Per\u00edodo 1' in html
        # Charts section with real data is present.
        assert 'Distribuci\u00f3n de rendimiento' in html
        assert 'Promedio por curso' in html
        assert 'id="bajo-rendimiento"' in html

    def test_rector_panel_student_count_is_real(self, client, csrf):
        conn = db()
        total = conn.execute('SELECT COUNT(*) as c FROM alumnos WHERE activo=1').fetchone()['c']
        conn.close()
        self._rector_session(client)
        r = client.get(f'/{SLUG}/rector/panel')
        html = r.get_data(as_text=True)
        assert f'<div class="dval">{total}</div>' in html or f'>{total}</div>' in html


# ── ESTUDIANTE ────────────────────────────────────────────────────────────

class TestStudentDashboard:
    def test_student_dashboard_shows_period_and_counts(self, client, csrf):
        conn = db()
        alumno = conn.execute("SELECT * FROM alumnos WHERE id=1").fetchone()
        inasistencias = conn.execute(
            "SELECT COUNT(*) as c FROM asistencia WHERE aid=1 AND estado IN ('A','E','X','S')",
            ).fetchone()['c']
        conn.close()
        assert alumno is not None
        with client.session_transaction() as sess:
            sess[f'rol_{SLUG}'] = 'estudiante'
            sess[f'alumno_id_{SLUG}'] = alumno['id']
            sess[f'alumno_nombre_{SLUG}'] = alumno['nombre']
            sess[f'alumno_curso_{SLUG}'] = alumno['curso']
            sess[f'alumno_jornada_{SLUG}'] = alumno['jornada']
            sess['_csrf_token'] = CSRF
        r = client.get(f'/{SLUG}/estudiante')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'Per\u00edodo 1 de' in html
        assert 'Inasistencias' in html
        assert 'Pr\u00f3ximas evaluaciones' in html
        assert str(inasistencias) in html
        assert 'Resumen acad\u00e9mico' in html


# ── PADRE ─────────────────────────────────────────────────────────────────

class TestParentDashboard:
    def test_parent_horario_observaciones_historial(self, client, csrf):
        hijo = seed_p6_parent()
        assert hijo is not None
        with client.session_transaction() as sess:
            sess[f'padre_id_{SLUG}'] = 101
            sess['_csrf_token'] = CSRF

        r = client.get(f'/{SLUG}/portal/horario/{hijo["id"]}')
        assert r.status_code == 200
        assert 'horario' in r.get_json()

        r = client.get(f'/{SLUG}/portal/observaciones/{hijo["id"]}')
        assert r.status_code == 200
        assert 'observaciones' in r.get_json()

        r = client.get(f'/{SLUG}/portal/historial/{hijo["id"]}')
        assert r.status_code == 200
        body = r.get_json()
        assert 'periodos' in body['historial']
        assert 'totales' in body['historial']

    def test_parent_guard_blocks_unlinked_child(self, client, csrf):
        seed_p6_parent()
        with client.session_transaction() as sess:
            sess[f'padre_id_{SLUG}'] = 101
            sess['_csrf_token'] = CSRF
        for url in [f'/{SLUG}/portal/horario/2', f'/{SLUG}/portal/observaciones/2',
                    f'/{SLUG}/portal/historial/2']:
            assert client.get(url).status_code == 403, url

    def test_parent_comunicados_have_fecha_creacion(self, client, csrf):
        conn = db()
        conn.execute(
            '''INSERT INTO comunicaciones (rector_id, titulo, contenido, destinatario_tipo,
               destinatario_valor, estado, fecha_creacion)
               VALUES (99,'P6 Comunicado','Contenido','todo_colegio','','publicado',
               ?)''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        conn.commit()
        conn.close()
        with client.session_transaction() as sess:
            sess[f'padre_id_{SLUG}'] = 101
            sess['_csrf_token'] = CSRF
        r = client.get(f'/{SLUG}/portal/comunicados')
        assert r.status_code == 200
        comunicados = r.get_json()['comunicados']
        assert any(c.get('titulo') == 'P6 Comunicado' and 'fecha_creacion' in c for c in comunicados)


# ── DIRECTORA ─────────────────────────────────────────────────────────────

class TestDirectoraDashboard:
    def test_directora_panel_kpi_row(self, client, csrf):
        conn = db()
        dir_id = conn.execute("SELECT id FROM directoras WHERE usuario='directora'").fetchone()['id']
        conn.close()
        with client.session_transaction() as sess:
            sess[f'directora_id_{SLUG}'] = dir_id
            sess['_csrf_token'] = CSRF
        r = client.get(f'/{SLUG}/directora/panel')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'Indicadores del per\u00edodo' in html
        assert 'Aprobados' in html
        assert 'Reprobados' in html
        assert 'table-consolidada' in html
