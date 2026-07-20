import os
from dataclasses import dataclass, field


@dataclass
class BaseSettings:
    # ── Paths ──
    _basedir: str = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    DB_FOLDER: str = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'colegios_db')
    MASTER_DB: str = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'master.db')
    LOGO_FOLDER: str = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'static', 'logos')

    # ── Env vars ──
    ENV: str = os.environ.get('FLASK_ENV', 'production')
    SECRET_KEY: str = (os.environ.get('SECRET_KEY') or '').strip()
    ADMIN_PASSWORD: str = (os.environ.get('ADMIN_PASSWORD') or '').strip()
    SENDGRID_API_KEY: str = (os.environ.get('SENDGRID_API_KEY') or '').strip()
    EMAIL_ORIGEN: str = (os.environ.get('EMAIL_ORIGEN') or 'lumini.appag@gmail.com').strip()
    PORT: int = int(os.environ.get('PORT', 8000))
    SESSION_COOKIE_SECURE: bool = (
        os.environ.get('SESSION_COOKIE_SECURE', '').lower() in ('true', '1', 'yes')
        if os.environ.get('SESSION_COOKIE_SECURE') else True
    )

    # ── Domain constants ──
    JORNADAS: list = field(default_factory=lambda: ['Mañana', 'Tarde', 'Nocturna'])
    MATERIAS: list = field(default_factory=lambda: [
        'Artes', 'Matemáticas', 'Cipol y Econ', 'Física', 'Química',
        'Español', 'Inglés', 'Biología', 'Sociales',
        'Tecnología e Informática', 'Filosofía', 'Educación Física',
    ])
    PREGUNTAS_SECRETAS: list = field(default_factory=lambda: [
        '¿Cuál es el nombre de tu mascota?',
        '¿En qué ciudad naciste?',
        '¿Cuál es el nombre de tu colegio favorito?',
        '¿Cuál es tu comida favorita?',
        '¿Cuál es el nombre de tu mejor amigo(a)?',
        '¿Cuál es tu color favorito?',
        '¿Cuál es el nombre de tu madre?',
        '¿Cuál es tu deporte favorito?',
    ])
    SCHEMA_VERSION: int = 20

    # ── Flask defaults ──
    SEND_FILE_MAX_AGE_DEFAULT: int = 86400 * 7
    PERMANENT_SESSION_LIFETIME_HOURS: int = 4
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = 'Lax'
    JSON_AS_ASCII: bool = False
    MAX_CONTENT_LENGTH: int = 2 * 1024 * 1024
    COMPRESS_ALGORITHM: str = 'gzip'
    COMPRESS_LEVEL: int = 6
    COMPRESS_MIN_SIZE: int = 500
