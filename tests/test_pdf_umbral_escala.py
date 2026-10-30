"""Regresión — coherencia del umbral de aprobación del boletín PDF con la escala.

Antes: `app/infra/pdf.py` calculaba el estado Aprobado/Reprobado usando
`nota_minima_aprobar` SIN adaptarlo cuando `escala_max > 5.0`, a diferencia de
`app/infra/dashboard.py`, `app/routes/rector_routes.py` y
`app/routes/directora_routes.py`, que aplican
`if escala_max > 5.0: nota_minima_aprobar /= 2.0`.

Estas pruebas ejercitan `generar_pdf_alumno` real y leen el estado que se imprime
en la tabla resumen del boletín (capturando el "story" de reportlab), demostrando
que escalas <= 5 y > 5 producen el mismo estado para la misma nota.
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('ENV', 'development')

import pytest

reportlab = pytest.importorskip('reportlab')
from reportlab.platypus import SimpleDocTemplate  # noqa: E402

from app.infra import pdf as pdf_mod  # noqa: E402
import app.infra.database as dbmod  # noqa: E402


ESCALA_5 = {'tipo_evaluacion': 'numerica', 'escala_min': 1.0,
            'escala_max': 5.0, 'nota_minima_aprobar': 3.0}
ESCALA_10 = {'tipo_evaluacion': 'numerica', 'escala_min': 1.0,
             'escala_max': 10.0, 'nota_minima_aprobar': 6.0}


def _conn(nota):
    c = sqlite3.connect(':memory:')
    c.row_factory = sqlite3.Row
    c.executescript('''
        CREATE TABLE actividades (
            id INTEGER PRIMARY KEY, materia TEXT, curso TEXT, jornada TEXT, periodo INTEGER);
        CREATE TABLE notas (aid INTEGER, actividad_id INTEGER, val REAL);
        CREATE TABLE evaluaciones (
            aid INTEGER, materia TEXT, jornada TEXT, evaluacion REAL,
            autoevaluacion REAL, periodo INTEGER);
    ''')
    c.execute("INSERT INTO actividades (id, materia, curso, jornada, periodo) "
              "VALUES (1, 'Matemáticas', 'Primero A', 'Mañana', 1)")
    c.execute("INSERT INTO notas (aid, actividad_id, val) VALUES (1, 1, ?)", (nota,))
    c.execute("INSERT INTO evaluaciones "
              "(aid, materia, jornada, evaluacion, autoevaluacion, periodo) "
              "VALUES (1, 'Matemáticas', 'Mañana', ?, ?, 1)", (nota, nota))
    c.commit()
    return c


def _estado_pdf(monkeypatch, cfg, nota):
    """Genera el boletín y devuelve (estado, promedio) leídos de la tabla resumen."""
    capturado = []
    monkeypatch.setattr(dbmod, 'config_get', lambda slug: dict(cfg))
    monkeypatch.setattr(SimpleDocTemplate, 'build',
                        lambda self, story, *a, **k: capturado.append(list(story)))
    conn = _conn(nota)
    try:
        pdf_mod.generar_pdf_alumno(
            {'id': 1, 'nombre': 'Alumno Test'}, 'testcolegio',
            {'nombre': 'Colegio Test', 'primary_color': '#6c63ff'},
            'Primero A', 'Mañana', 1, conn)
    finally:
        conn.close()
    assert capturado, 'no se capturó el contenido del PDF'
    for flujo in capturado[0]:
        celdas = getattr(flujo, '_cellvalues', None)
        if celdas and celdas[0] and celdas[0][0] == 'PROMEDIO GENERAL':
            return celdas[0][3], float(celdas[0][1])
    raise AssertionError('no se encontró la tabla resumen en el boletín')


class TestPDFUmbralEscala:
    @pytest.mark.parametrize('nota,esperado', [
        (3.5, 'Aprobado'),   # >= umbral efectivo 3.0 y < umbral sin ajustar 6.0
        (2.0, 'Reprobado'),  # < umbral efectivo 3.0
    ])
    def test_estado_coherente_entre_escalas(self, monkeypatch, nota, esperado):
        estado5, prom5 = _estado_pdf(monkeypatch, ESCALA_5, nota)
        estado10, prom10 = _estado_pdf(monkeypatch, ESCALA_10, nota)
        assert prom5 == pytest.approx(nota)
        assert prom10 == pytest.approx(nota)
        assert estado5 == esperado
        assert estado10 == esperado
        # Coherencia: la misma nota produce el mismo estado en ambas escalas.
        assert estado5 == estado10

    def test_escala_10_usa_umbral_mitad(self, monkeypatch):
        # 3.5 aprueba SOLO si el umbral 6.0 se reduce a 3.0 (convención escala > 5).
        estado10, _ = _estado_pdf(monkeypatch, ESCALA_10, 3.5)
        assert estado10 == 'Aprobado'
        # Con el umbral sin ajustar (6.0) la misma nota sería 'Reprobado' (3.5 < 6.0).
        assert 3.5 < float(ESCALA_10['nota_minima_aprobar'])

    def test_escala_justo_5_no_ajusta(self, monkeypatch):
        # escala_max == 5.0 NO se divide; umbral 3.0 -> 3.5 aprueba.
        estado5, _ = _estado_pdf(monkeypatch, ESCALA_5, 3.5)
        assert estado5 == 'Aprobado'
