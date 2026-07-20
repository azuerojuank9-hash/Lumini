"""
Backward-compatible re-exports from config/ package.
All constants now live in config/ package for environment-aware settings.
"""
from typing import List
from config import settings

DB_FOLDER: str = settings.DB_FOLDER
MASTER_DB: str = settings.MASTER_DB
LOGO_FOLDER: str = settings.LOGO_FOLDER

ENV: str = settings.ENV
ADMIN_PASSWORD: str = settings.ADMIN_PASSWORD
SENDGRID_API_KEY: str = settings.SENDGRID_API_KEY
EMAIL_ORIGEN: str = settings.EMAIL_ORIGEN

JORNADAS: List[str] = settings.JORNADAS
MATERIAS: List[str] = settings.MATERIAS
PREGUNTAS_SECRETAS: List[str] = settings.PREGUNTAS_SECRETAS
SCHEMA_VERSION: int = settings.SCHEMA_VERSION
