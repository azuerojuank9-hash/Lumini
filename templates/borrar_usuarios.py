"""
Ejecuta este script desde la consola de PythonAnywhere:
    python borrar_usuarios.py

Borra TODOS los profesores y directoras de TODOS los colegios.
Los alumnos, notas, asistencia y demás datos NO se tocan.
"""

import sqlite3, os

DB_FOLDER = os.path.join(os.path.dirname(__file__), 'colegios_db')

# Listar todas las bases de datos de colegios
dbs = [f for f in os.listdir(DB_FOLDER) if f.endswith('.db') and not f.endswith('.bak')]

total_profs = 0
total_dirs  = 0

for db_file in dbs:
    slug = db_file.replace('.db', '')
    path = os.path.join(DB_FOLDER, db_file)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    # Contar antes
    n_profs = conn.execute('SELECT COUNT(*) FROM profesores').fetchone()[0]
    n_dirs  = conn.execute('SELECT COUNT(*) FROM directoras').fetchone()[0]

    # Borrar
    conn.execute('DELETE FROM profesores')
    conn.execute('DELETE FROM directoras')
    conn.execute('DELETE FROM asignaciones_materia')
    conn.execute('DELETE FROM asignaciones_curso')
    conn.commit()
    conn.close()

    print(f'[{slug}] Borrados: {n_profs} profesores, {n_dirs} directoras')
    total_profs += n_profs
    total_dirs  += n_dirs

print(f'\nTotal: {total_profs} profesores y {total_dirs} directoras eliminados.')
print('Alumnos, notas, asistencia y demás datos intactos.')
