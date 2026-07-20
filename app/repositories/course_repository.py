def add_cursos_to_profesor(conn, profesor_id, materia, jornada, cursos):
    for c in cursos:
        if c:
            conn.execute(
                'INSERT OR IGNORE INTO asignaciones_curso (profesor_id,materia,jornada,curso) VALUES (?,?,?,?)',
                (profesor_id, materia, jornada, c))


def remove_curso_from_profesor(conn, profesor_id, materia, jornada, curso):
    conn.execute(
        'DELETE FROM asignaciones_curso WHERE profesor_id=? AND materia=? AND jornada=? AND curso=?',
        (profesor_id, materia, jornada, curso))


def get_profesores_destino(conn, materia, jornada, exclude_profesor_id):
    return conn.execute(
        '''SELECT p.id, p.nombre FROM profesores p
           JOIN asignaciones_materia am ON am.profesor_id=p.id
           WHERE am.materia=? AND am.jornada=? AND p.id!=? AND p.activo=1
           ORDER BY p.nombre''',
        (materia, jornada, exclude_profesor_id)).fetchall()


def transfer_actividades(conn, from_pid, to_pid, materia, jornada, curso, periodo):
    conn.execute(
        'UPDATE actividades SET profesor_id=? WHERE profesor_id=? AND materia=? AND jornada=? AND curso=? AND COALESCE(periodo,1)=?',
        (to_pid, from_pid, materia, jornada, curso, periodo))


def transfer_evaluaciones(conn, from_pid, to_pid, materia, jornada, curso, periodo, jornada_curso):
    conn.execute(
        'UPDATE evaluaciones SET profesor_id=? WHERE profesor_id=? AND materia=? AND jornada=? AND COALESCE(periodo,1)=? AND aid IN (SELECT id FROM alumnos WHERE curso=? AND jornada=?)',
        (to_pid, from_pid, materia, jornada, periodo, curso, jornada_curso))


def copy_asignacion_curso(conn, profesor_id, materia, jornada, curso):
    conn.execute(
        'INSERT OR IGNORE INTO asignaciones_curso (profesor_id,materia,jornada,curso) VALUES (?,?,?,?)',
        (profesor_id, materia, jornada, curso))


def delete_asignacion_curso(conn, profesor_id, materia, jornada, curso):
    conn.execute(
        'DELETE FROM asignaciones_curso WHERE profesor_id=? AND materia=? AND jornada=? AND curso=?',
        (profesor_id, materia, jornada, curso))
