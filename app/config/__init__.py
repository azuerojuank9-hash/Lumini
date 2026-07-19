import os

_basedir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

DB_FOLDER = os.path.join(_basedir, 'colegios_db')
MASTER_DB = os.path.join(_basedir, 'master.db')
LOGO_FOLDER = os.path.join(_basedir, 'static', 'logos')

JORNADAS = ['Mañana', 'Tarde', 'Nocturna']

MATERIAS = [
    'Artes', 'Matematicas', 'Cipol y Econ', 'Fisica', 'Quimica',
    'Espanol', 'Ingles', 'Biologia', 'Sociales',
    'Tecnologia e Informatica', 'Filosofia', 'Educacion Fisica'
]

PREGUNTAS_SECRETAS = [
    'Cual es el nombre de tu mascota?',
    'En que ciudad naciste?',
    'Cual es el nombre de tu colegio favorito?',
    'Cual es tu comida favorita?',
    'Cual es el nombre de tu mejor amigo(a)?',
    'Cual es tu color favorito?',
    'Cual es el nombre de tu madre?',
    'Cual es tu deporte favorito?',
]

SCHEMA_VERSION = 20
