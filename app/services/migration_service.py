import csv
import io
import logging

from app.repositories.migration_repository import insert_actividad_migrada, insert_alumno

logger = logging.getLogger(__name__)


def preview_migration(contenido, tipo):
    lines = contenido.strip().split('\n')
    reader = csv.DictReader(io.StringIO(contenido))
    headers = reader.fieldnames
    rows = []
    for i, row in enumerate(reader):
        if i >= 10:
            break
        rows.append(dict(row))
    sugg = {}
    if tipo == 'estudiantes':
        name_cols = [h for h in headers if any(x in h.lower() for x in ['nombre', 'name', 'alumno', 'estudiante'])]
        if name_cols:
            sugg['nombre'] = name_cols[0]
        curso_cols = [h for h in headers if any(x in h.lower() for x in ['curso', 'grado', 'grade', 'salon'])]
        if curso_cols:
            sugg['curso'] = curso_cols[0]
    elif tipo == 'notas':
        name_cols = [h for h in headers if any(x in h.lower() for x in ['nombre', 'name', 'alumno'])]
        if name_cols:
            sugg['nombre'] = name_cols[0]
        note_cols = [h for h in headers if any(x in h.lower() for x in ['nota', 'calif', 'grade', 'puntaje', 'val'])]
        if note_cols:
            sugg['nota'] = note_cols[0]
    return headers, rows, sugg, len(lines) - 1


def execute_migration(conn, contenido, tipo, mapeo, profesor_id, materia, jornada):
    reader = csv.DictReader(io.StringIO(contenido))
    count = 0
    if tipo == 'estudiantes':
        nombre_col = mapeo.get('nombre', 'nombre')
        curso_col = mapeo.get('curso', 'curso')
        for row in reader:
            nombre = row.get(nombre_col, '').strip()
            curso = row.get(curso_col, '')
            if nombre:
                insert_alumno(conn, nombre, curso, jornada)
                count += 1
    elif tipo == 'actividades':
        nombre_col = mapeo.get('nombre', 'nombre')
        tipo_col = mapeo.get('tipo', 'tipo')
        peso_col = mapeo.get('peso', 'peso')
        curso_col = mapeo.get('curso', 'curso')
        for row in reader:
            nombre = row.get(nombre_col, '').strip()
            curso = row.get(curso_col, '')
            tipo_act = row.get(tipo_col, 'tarea')
            peso = float(row.get(peso_col, 10)) if row.get(peso_col) else 10
            if nombre:
                insert_actividad_migrada(conn, profesor_id, materia, jornada, curso, nombre, tipo_act, peso)
                count += 1
    conn.commit()
    return count
