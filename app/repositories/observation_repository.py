def create_observation(conn, aid, materia, texto):
    conn.execute(
        'INSERT INTO observaciones (aid,materia,texto,fecha) VALUES (?,?,?,date("now"))',
        (aid, materia, texto))
    return conn.execute(
        'SELECT id, materia, texto, fecha FROM observaciones WHERE aid=? AND materia=? ORDER BY id DESC LIMIT 1',
        (aid, materia)).fetchone()


def get_observation(conn, id_o, materia):
    return conn.execute(
        'SELECT id, aid, materia, texto, fecha FROM observaciones WHERE id=? AND materia=?',
        (id_o, materia)).fetchone()


def get_observation_by_id(conn, id_o):
    return conn.execute(
        'SELECT id, aid, materia, texto FROM observaciones WHERE id=?', (id_o,)).fetchone()


def update_observation(conn, id_o, texto):
    conn.execute('UPDATE observaciones SET texto=? WHERE id=?', (texto, id_o))


def delete_observation(conn, id_o):
    conn.execute('DELETE FROM observaciones WHERE id=?', (id_o,))


def student_belongs_to_cursos(conn, aid, cursos_prof, jornada):
    placeholders = ','.join('?' * len(cursos_prof))
    return conn.execute(
        f'SELECT id FROM alumnos WHERE id=? AND curso IN ({placeholders}) AND jornada=? AND activo=1',
        (aid, *cursos_prof, jornada)).fetchone() is not None
