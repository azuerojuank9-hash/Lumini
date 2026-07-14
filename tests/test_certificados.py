import os, sys, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'
from flask_app import app
import pytest

TEST_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'colegios_db', 'testcolegio.db')

@pytest.fixture
def conn():
    c = sqlite3.connect(TEST_DB)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    yield c
    c.close()

def test_constancia_estudio(conn):
    from utils.certificates import generar_constancia_estudio
    alumno = {'id': 1, 'nombre': 'Alumno Uno', 'curso': 'Primero A', 'jornada': 'Mañana'}
    colegio = {'nombre': 'Test School', 'municipio': 'Bogotá'}
    buf = generar_constancia_estudio(alumno, colegio, 'Rector Test')
    assert buf is not None
    data = buf.read()
    assert len(data) > 100
    assert data.startswith(b'%PDF')

def test_certificado_estudio(conn):
    from utils.certificates import generar_certificado_estudio
    alumno = {'id': 1, 'nombre': 'Alumno Uno', 'curso': 'Primero A'}
    colegio = {'nombre': 'Test School'}
    materias = [{'nombre': 'Matematicas', 'nota': 4.5}, {'nombre': 'Espanol', 'nota': 3.8}]
    buf = generar_certificado_estudio(alumno, colegio, materias, 4.15, 'Rector Test')
    assert buf is not None
    data = buf.read()
    assert len(data) > 100
    assert data.startswith(b'%PDF')

def test_paz_y_salvo(conn):
    from utils.certificates import generar_paz_y_salvo
    alumno = {'id': 1, 'nombre': 'Alumno Uno'}
    colegio = {'nombre': 'Test School'}
    buf = generar_paz_y_salvo(alumno, colegio, 'Rector Test')
    assert buf is not None
    data = buf.read()
    assert len(data) > 100
    assert data.startswith(b'%PDF')

def test_certificado_conducta(conn):
    from utils.certificates import generar_certificado_conducta
    alumno = {'id': 1, 'nombre': 'Alumno Uno', 'curso': 'Primero A'}
    colegio = {'nombre': 'Test School'}
    observaciones = [{'texto': 'comportamiento positivo'}, {'texto': 'buen trabajo'}]
    buf = generar_certificado_conducta(alumno, colegio, observaciones, 'Rector Test')
    assert buf is not None
    data = buf.read()
    assert len(data) > 100
    assert data.startswith(b'%PDF')

def test_certificado_conducta_alta(conn):
    from utils.certificates import generar_certificado_conducta
    alumno = {'id': 1, 'nombre': 'Alumno Uno', 'curso': 'Primero A'}
    colegio = {'nombre': 'Test School'}
    observaciones = [{'texto': 'mala conducta'}, {'texto': 'reportado'}, {'texto': 'llamado'}, {'texto': 'sancion'}]
    buf = generar_certificado_conducta(alumno, colegio, observaciones, 'Rector Test')
    data = buf.read()
    assert len(data) > 100

def test_certificados_no_firma(conn):
    from utils.certificates import generar_constancia_estudio
    alumno = {'id': 1, 'nombre': 'Alumno Uno', 'curso': 'Primero A', 'jornada': 'Mañana'}
    colegio = {'nombre': 'Test School'}
    buf = generar_constancia_estudio(alumno, colegio)
    data = buf.read()
    assert len(data) > 100
    assert data.startswith(b'%PDF')
