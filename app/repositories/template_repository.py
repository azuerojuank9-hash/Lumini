def get_templates(conn, profesor_id):
    return conn.execute(
        'SELECT id, nombre, tipo, peso, descripcion, created_at FROM plantillas WHERE profesor_id=? ORDER BY nombre',
        (profesor_id,)).fetchall()


def create_template(conn, profesor_id, nombre, tipo, peso, descripcion):
    conn.execute(
        'INSERT INTO plantillas (profesor_id, nombre, tipo, peso, descripcion) VALUES (?,?,?,?,?)',
        (profesor_id, nombre, tipo, peso, descripcion))
    conn.commit()


def get_template_by_id(conn, tmpl_id, profesor_id):
    return conn.execute(
        'SELECT * FROM plantillas WHERE id=? AND profesor_id=?', (tmpl_id, profesor_id)).fetchone()


def delete_template(conn, tid, profesor_id):
    conn.execute('DELETE FROM plantillas WHERE id=? AND profesor_id=?', (tid, profesor_id))
    conn.commit()


def get_max_orden(conn, materia, jornada, curso, profesor_id):
    r = conn.execute(
        'SELECT COALESCE(MAX(orden),0) as mx FROM actividades WHERE materia=? AND jornada=? AND curso=? AND profesor_id=?',
        (materia, jornada, curso, profesor_id)).fetchone()
    return r['mx'] if r else 0


def insert_actividad_desde_plantilla(conn, profesor_id, materia, jornada, curso, periodo, nombre, tipo, peso, orden):
    conn.execute(
        'INSERT INTO actividades (profesor_id, materia, jornada, curso, periodo, nombre, tipo, peso, estado_act, orden) VALUES (?,?,?,?,?,?,?,?,?,?)',
        (profesor_id, materia, jornada, curso, periodo, nombre, tipo, peso, 'borrador', orden))
    conn.commit()
