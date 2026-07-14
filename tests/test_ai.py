import os, sys, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'
from flask_app import app, init_db
import pytest

TEST_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'colegios_db', 'testcolegio.db')

def seed():
    init_db('testcolegio')
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("DELETE FROM rectores WHERE usuario='ai_rector'")
    conn.execute("INSERT OR IGNORE INTO rectores (id, nombre, usuario, password, email, activo, es_principal) VALUES (?,?,?,?,?,?,?)",
                 (299, 'AI Rector', 'ai_rector', 'fake', 'ai@test.com', 1, 1))
    cur = conn.execute("SELECT id FROM alumnos WHERE id=299")
    if not cur.fetchone():
        conn.execute("INSERT INTO alumnos (id, nombre, curso, jornada, activo) VALUES (?,?,?,?,?)",
                     (299, 'AI Alumno', 'Primero A', 'Manana', 1))
    conn.execute("DELETE FROM notas WHERE aid=299")
    conn.execute("DELETE FROM asistencia WHERE aid=299")
    conn.commit()
    conn.close()

seed()

@pytest.fixture
def ai():
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    from services.ai import AIService
    yield AIService('testcolegio', conn)
    conn.close()

def test_ai_not_available(ai):
    assert ai.is_available() is False

def test_ai_predict_risk_bajo(ai):
    pred = ai.predict_risk(299)
    assert pred.riesgo in ('bajo', 'medio', 'alto')
    assert pred.estudiante_id == 299

def test_ai_predict_risk_alto(ai):
    ai.conn.execute("INSERT INTO notas (aid, actividad_id, val) VALUES (?,?,?)",
                    (299, 1, 1.5))
    ai.conn.commit()
    pred = ai.predict_risk(299)
    assert pred.riesgo == 'alto'
    assert pred.puntaje < 3.0
    assert any('bajo' in f.lower() for f in pred.factores)
    ai.conn.execute("DELETE FROM notas WHERE aid=299")
    ai.conn.commit()

def test_ai_generate_observation(ai):
    obs = ai.generate_observation(299)
    assert 'estudiante' in obs.lower()
    assert 'AI Alumno' in obs or 'académico' in obs

def test_ai_batch_risk_analysis(ai):
    results = ai.batch_risk_analysis()
    assert isinstance(results, list)

def test_ai_batch_risk_analysis_by_curso(ai):
    results = ai.batch_risk_analysis(curso='Primero A')
    assert isinstance(results, list)

def test_ai_recommend_courses(ai):
    recs = ai.recommend_courses(299)
    assert isinstance(recs, list)
