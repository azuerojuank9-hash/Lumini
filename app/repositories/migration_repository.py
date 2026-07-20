def insert_alumno(conn, nombre, curso, jornada):
    conn.execute('INSERT INTO alumnos (nombre, curso, jornada, activo) VALUES (?,?,?,1)', (nombre, curso, jornada))


def insert_actividad_migrada(conn, profesor_id, materia, jornada, curso, nombre, tipo_act, peso):
    conn.execute(
        "INSERT INTO actividades (profesor_id, materia, jornada, curso, nombre, tipo, peso, estado_act, orden) VALUES (?,?,?,?,?,?,?,?,"
        "(SELECT COALESCE(MAX(orden),0)+1 FROM actividades WHERE materia=? AND jornada=? AND curso=? AND profesor_id=?))",
        (profesor_id, materia, jornada, curso, nombre, tipo_act, peso, 'borrador', materia, jornada, curso, profesor_id))
