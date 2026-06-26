"""Seed a rector account into a colegio's database.
Usage: python seed_rector.py <slug> <nombre> <usuario> <password>
If the database doesn't exist, it will be created with all required tables.
"""
import sys, os, hashlib, secrets, sqlite3

DB_FOLDER = os.path.join(os.path.dirname(__file__), 'colegios_db')

def hash_pw(pw):
    sal = secrets.token_hex(16)
    return f"{sal}${hashlib.sha256((sal + pw).encode()).hexdigest()}"

TABLES = [
    '''CREATE TABLE IF NOT EXISTS rectores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL, usuario TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL, email TEXT DEFAULT '',
        activo INTEGER DEFAULT 1,
        pregunta_secreta TEXT DEFAULT '',
        respuesta_secreta TEXT DEFAULT '')''',
    '''CREATE TABLE IF NOT EXISTS comunicaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rector_id INTEGER NOT NULL, titulo TEXT NOT NULL,
        contenido TEXT NOT NULL, destinatario_tipo TEXT NOT NULL,
        destinatario_valor TEXT DEFAULT '', prioridad TEXT NOT NULL DEFAULT 'normal',
        estado TEXT NOT NULL DEFAULT 'borrador',
        fecha_creacion TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        fecha_programada TEXT DEFAULT NULL,
        fecha_publicacion TEXT DEFAULT NULL, activo INTEGER DEFAULT 1)''',
    '''CREATE TABLE IF NOT EXISTS comunicaciones_leidas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        comunicacion_id INTEGER NOT NULL, usuario_tipo TEXT NOT NULL,
        usuario_id INTEGER NOT NULL,
        fecha_lectura TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        UNIQUE(comunicacion_id, usuario_tipo, usuario_id))''',
    '''CREATE TABLE IF NOT EXISTS notificaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_tipo TEXT NOT NULL, usuario_id INTEGER NOT NULL,
        titulo TEXT NOT NULL, mensaje TEXT DEFAULT '',
        tipo TEXT NOT NULL DEFAULT 'info', link TEXT DEFAULT '',
        leida INTEGER DEFAULT 0,
        fecha_creacion TEXT NOT NULL DEFAULT (datetime('now','localtime')))''',
]

def init_tables(conn):
    for s in TABLES:
        conn.execute(s)
    conn.commit()

def main():
    if len(sys.argv) != 5:
        print("Usage: python seed_rector.py <slug> <nombre> <usuario> <password>")
        sys.exit(1)
    slug, nombre, usuario, password = sys.argv[1:5]
    os.makedirs(DB_FOLDER, exist_ok=True)
    db = os.path.join(DB_FOLDER, f'{slug}.db')
    create = not os.path.exists(db)
    conn = sqlite3.connect(db)
    conn.execute('PRAGMA foreign_keys=ON')
    if create:
        print(f"Creating new database: {db}")
    init_tables(conn)
    h = hash_pw(password)
    try:
        conn.execute(
            'INSERT OR IGNORE INTO rectores (nombre, usuario, password) VALUES (?, ?, ?)',
            (nombre, usuario, h))
        conn.commit()
        if conn.total_changes:
            print(f"Rector '{nombre}' ({usuario}) inserted into '{slug}'.")
        else:
            print(f"Rector '{usuario}' already exists in '{slug}'.")
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    main()
