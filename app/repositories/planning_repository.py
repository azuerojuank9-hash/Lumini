def get_actividades_origin(conn, materia, jornada, origen_curso, profesor_id):
    return conn.execute(
        'SELECT nombre, tipo, peso, fecha_limite, estado_act FROM actividades WHERE materia=? AND jornada=? AND curso=? AND profesor_id=? ORDER BY orden',
        (materia, jornada, origen_curso, profesor_id)).fetchall()


def get_next_orden(conn, materia, jornada, curso, profesor_id):
    r = conn.execute(
        'SELECT COALESCE(MAX(orden),0)+1 as nxt FROM actividades WHERE materia=? AND jornada=? AND curso=? AND profesor_id=?',
        (materia, jornada, curso, profesor_id)).fetchone()
    return r['nxt'] if r else 1


def copiar_actividad(conn, profesor_id, materia, jornada, destino_curso, act, orden):
    conn.execute(
        'INSERT INTO actividades (profesor_id, materia, jornada, curso, nombre, tipo, peso, fecha_limite, estado_act, orden) VALUES (?,?,?,?,?,?,?,?,?,?)',
        (profesor_id, materia, jornada, destino_curso, act['nombre'], act['tipo'], act['peso'], act['fecha_limite'], 'borrador', orden))
