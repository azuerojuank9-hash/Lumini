from app.models.schema import conectar


def create_student(conn, nombre, curso, jornada):
    conn.execute(
        'INSERT INTO alumnos (nombre,curso,jornada,num_curso,activo) VALUES (?,?,?,0,1)',
        (nombre, curso, jornada))


def get_student_curso(conn, aid):
    return conn.execute('SELECT curso FROM alumnos WHERE id=?', (aid,)).fetchone()


def renumber_students(conn, curso, jornada):
    todos = conn.execute(
        'SELECT id FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre COLLATE NOCASE',
        (curso, jornada)).fetchall()
    for i, a in enumerate(todos, 1):
        conn.execute('UPDATE alumnos SET num_curso=? WHERE id=?', (i, a['id']))


def archive_student(conn, aid):
    conn.execute('UPDATE alumnos SET activo=0 WHERE id=?', (aid,))


def reactivate_student(conn, aid):
    conn.execute('UPDATE alumnos SET activo=1 WHERE id=?', (aid,))


def delete_student(conn, aid):
    conn.execute('DELETE FROM alumnos WHERE id=?', (aid,))
    conn.execute('DELETE FROM notas WHERE aid=?', (aid,))
    conn.execute('DELETE FROM evaluaciones WHERE aid=?', (aid,))
    conn.execute('DELETE FROM asistencia WHERE aid=?', (aid,))
    conn.execute('DELETE FROM observaciones WHERE aid=?', (aid,))


def get_archived_students(conn, curso, jornada):
    return conn.execute(
        'SELECT * FROM alumnos WHERE curso=? AND jornada=? AND activo=0 ORDER BY nombre COLLATE NOCASE',
        (curso, jornada)).fetchall()


def get_active_profesores(conn):
    return conn.execute(
        'SELECT * FROM profesores WHERE activo=1 ORDER BY nombre COLLATE NOCASE').fetchall()


def get_archived_profesores(conn):
    return conn.execute(
        'SELECT * FROM profesores WHERE activo=0 ORDER BY nombre COLLATE NOCASE').fetchall()


def get_asignaciones_materia(conn):
    return conn.execute(
        'SELECT id, profesor_id, materia, jornada FROM asignaciones_materia ORDER BY jornada, materia').fetchall()


def get_asignaciones_curso(conn):
    return conn.execute(
        'SELECT profesor_id, materia, jornada, curso FROM asignaciones_curso').fetchall()


def get_other_active_profesores_by_mat_jor(conn):
    return conn.execute(
        '''SELECT p2.id, p2.nombre, am.materia, am.jornada
           FROM profesores p2
           JOIN asignaciones_materia am ON am.profesor_id=p2.id
           WHERE p2.activo=1''').fetchall()


def archive_profesor(conn, pid):
    conn.execute('UPDATE profesores SET activo=0 WHERE id=?', (pid,))


def reactivate_profesor(conn, pid):
    conn.execute('UPDATE profesores SET activo=1 WHERE id=?', (pid,))


def delete_profesor(conn, pid):
    conn.execute('DELETE FROM profesores WHERE id=?', (pid,))
    conn.execute('DELETE FROM asignaciones_materia WHERE profesor_id=?', (pid,))
    conn.execute('DELETE FROM asignaciones_curso WHERE profesor_id=?', (pid,))


def reasignar_actividades(conn, from_pid, to_pid, curso, materia, jornada):
    conn.execute(
        'UPDATE actividades SET profesor_id=? WHERE profesor_id=? AND materia=? AND jornada=? AND curso=?',
        (to_pid, from_pid, materia, jornada, curso))


def reasignar_evaluaciones(conn, from_pid, to_pid, curso, jornada):
    conn.execute(
        'UPDATE evaluaciones SET profesor_id=? WHERE profesor_id=? AND materia=? AND jornada=? AND aid IN (SELECT id FROM alumnos WHERE curso=? AND jornada=?)',
        (to_pid, from_pid, None, None, curso, jornada))


def copy_asignacion_curso(conn, to_pid, materia, jornada, curso):
    conn.execute(
        'INSERT OR IGNORE INTO asignaciones_curso (profesor_id,materia,jornada,curso) VALUES (?,?,?,?)',
        (to_pid, materia, jornada, curso))


def remove_asignacion_curso(conn, from_pid, materia, jornada, curso):
    conn.execute(
        'DELETE FROM asignaciones_curso WHERE profesor_id=? AND materia=? AND jornada=? AND curso=?',
        (from_pid, materia, jornada, curso))


def ensure_asignacion_materia(conn, to_pid, materia, jornada):
    conn.execute(
        'INSERT OR IGNORE INTO asignaciones_materia (profesor_id,materia,jornada) VALUES (?,?,?)',
        (to_pid, materia, jornada))


def get_compromiso_curso(conn, cid):
    return conn.execute('SELECT curso FROM compromisos WHERE id=?', (cid,)).fetchone()


def delete_compromiso(conn, cid, materia):
    conn.execute('DELETE FROM compromisos WHERE id=? AND materia=?', (cid, materia))


def create_compromiso(conn, titulo, fecha, materia, curso, jornada):
    conn.execute(
        'INSERT INTO compromisos (titulo,fecha,materia,curso,jornada) VALUES (?,?,?,?,?)',
        (titulo, fecha, materia, curso, jornada))


def get_cursos_list(conn, profesor_id, materia, jornada):
    return [r['curso'] for r in conn.execute(
        'SELECT DISTINCT curso FROM asignaciones_curso WHERE profesor_id=? AND materia=? AND jornada=?',
        (profesor_id, materia, jornada)).fetchall()]


def get_alumno(conn, aid):
    return conn.execute('SELECT * FROM alumnos WHERE id=? AND activo=1', (aid,)).fetchone()


def get_compromisos_curso(conn, curso, jornada):
    return conn.execute(
        'SELECT * FROM compromisos WHERE curso=? AND jornada=? ORDER BY fecha, materia',
        (curso, jornada)).fetchall()


def get_notas_estudiante(conn, aid, curso, jornada, periodo):
    return conn.execute(
        '''SELECT ac.materia, ac.nombre as act_nombre, n.val
           FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
           WHERE n.aid=? AND ac.curso=? AND ac.jornada=?
           AND COALESCE(ac.periodo,1)=?
           ORDER BY ac.materia, ac.orden''',
        (aid, curso, jornada, periodo)).fetchall()


def get_evaluaciones_estudiante(conn, aid, periodo):
    return conn.execute(
        'SELECT materia, evaluacion, autoevaluacion FROM evaluaciones WHERE aid=? AND COALESCE(periodo,1)=?',
        (aid, periodo)).fetchall()


def get_asistencia_estudiante(conn, aid):
    return conn.execute(
        'SELECT fecha, estado, observacion FROM asistencia WHERE aid=? ORDER BY fecha', (aid,)).fetchall()


def get_observaciones_estudiante(conn, aid):
    return conn.execute(
        'SELECT materia, texto, fecha FROM observaciones WHERE aid=? ORDER BY fecha DESC', (aid,)).fetchall()


def get_horario_curso(conn, curso, jornada):
    return conn.execute(
        'SELECT dia, franja, num, materia, profesor FROM horarios_curso WHERE curso=? AND jornada=?',
        (curso, jornada)).fetchall()
