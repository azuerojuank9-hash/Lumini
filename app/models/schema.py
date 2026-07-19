"""Database schema and migration functions.

During Phase 1, this module re-exports from flask_app.py.
Over time, functions will be migrated here directly.
"""

import os, sys
import sqlite3
import logging

logger = logging.getLogger(__name__)

# Paths and constants (mirrored from flask_app for import safety)
_basedir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
DB_FOLDER = os.path.join(_basedir, 'colegios_db')
MASTER_DB = os.path.join(_basedir, 'master.db')
SCHEMA_VERSION = 20


def db_path(slug):
    return os.path.join(DB_FOLDER, f'{slug}.db')


def conectar(slug):
    conn = sqlite3.connect(db_path(slug), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def conectar_master():
    conn = sqlite3.connect(MASTER_DB, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_master_db():
    """Proxy a flask_app.init_master_db si existe, sino ejecuta inline."""
    import flask_app
    return flask_app.init_master_db()


def init_db(slug):
    """Proxy a flask_app.init_db si existe, sino ejecuta inline."""
    import flask_app
    return flask_app.init_db(slug)


def _ejecutar_migraciones(slug, conn):
    """Proxy a flask_app._ejecutar_migraciones."""
    import flask_app
    return flask_app._ejecutar_migraciones(slug, conn)


def migrar_db(slug):
    """Proxy a flask_app.migrar_db."""
    import flask_app
    return flask_app.migrar_db(slug)
