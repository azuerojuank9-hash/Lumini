def get_students_by_curso(conn, curso, jornada):
    return conn.execute(
        'SELECT id, nombre, num_curso FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre COLLATE NOCASE',
        (curso, jornada)).fetchall()


def get_student_ids_by_curso(conn, curso, jornada):
    return conn.execute(
        'SELECT id FROM alumnos WHERE curso=? AND jornada=? AND activo=1',
        (curso, jornada)).fetchall()


def get_asistencia_for_date(conn, fecha, aids):
    placeholders = ','.join('?' * len(aids))
    return conn.execute(
        f'SELECT aid, estado, observacion, hora FROM asistencia WHERE fecha=? AND aid IN ({placeholders})',
        (fecha,) + tuple(aids)).fetchall()


def get_asistencia_stats(conn, aids):
    placeholders = ','.join('?' * len(aids))
    return conn.execute(
        f'SELECT estado, COUNT(*) as c FROM asistencia WHERE aid IN ({placeholders}) GROUP BY estado',
        aids).fetchall()


def get_asistencia_abs_consec(conn, aids):
    placeholders = ','.join('?' * len(aids))
    return conn.execute(
        f"SELECT aid, fecha FROM asistencia WHERE aid IN ({placeholders}) AND estado='A' AND fecha >= date('now','-30 days') ORDER BY aid, fecha",
        aids).fetchall()


def get_asistencia_tardanzas(conn, aids):
    placeholders = ','.join('?' * len(aids))
    return conn.execute(
        f'SELECT aid, COUNT(*) as c FROM asistencia WHERE aid IN ({placeholders}) AND estado="T" GROUP BY aid',
        aids).fetchall()


def get_asistencia_all_stats(conn, aids):
    placeholders = ','.join('?' * len(aids))
    return conn.execute(
        f'SELECT aid, estado, COUNT(*) as c FROM asistencia WHERE aid IN ({placeholders}) GROUP BY aid, estado',
        aids).fetchall()


def get_asistencia_all_dates(conn, aids):
    placeholders = ','.join('?' * len(aids))
    return conn.execute(
        f'SELECT fecha, estado FROM asistencia WHERE aid IN ({placeholders}) ORDER BY fecha',
        aids).fetchall()


def get_asistencia_full(conn, aids):
    placeholders = ','.join('?' * len(aids))
    return conn.execute(
        f'SELECT aid, fecha, estado, observacion FROM asistencia WHERE aid IN ({placeholders}) ORDER BY aid, fecha',
        aids).fetchall()


def upsert_asistencia(conn, aid, fecha, estado, observacion, hora, usuario_tipo, usuario_id):
    if fecha:
        conn.execute('''INSERT INTO asistencia (aid,fecha,estado,observacion,hora,usuario_tipo,usuario_id)
                        VALUES (?,?,?,?,?,?,?)
                        ON CONFLICT(aid,fecha) DO UPDATE SET estado=excluded.estado,
                                                             observacion=excluded.observacion,
                                                             hora=excluded.hora,
                                                             usuario_tipo=excluded.usuario_tipo,
                                                             usuario_id=excluded.usuario_id''',
                     (aid, fecha, estado, observacion, hora, usuario_tipo, usuario_id))
    else:
        conn.execute('''INSERT INTO asistencia (aid,fecha,estado,observacion,hora,usuario_tipo,usuario_id)
                        VALUES (?,date("now"),?,?,?,?,?)
                        ON CONFLICT(aid,fecha) DO UPDATE SET estado=excluded.estado,
                                                             observacion=excluded.observacion,
                                                             hora=excluded.hora,
                                                             usuario_tipo=excluded.usuario_tipo,
                                                             usuario_id=excluded.usuario_id''',
                     (aid, estado, observacion, hora, usuario_tipo, usuario_id))


def verify_student_in_cursos(conn, aid, cursos_prof, jornada):
    placeholders = ','.join('?' * len(cursos_prof))
    return conn.execute(
        'SELECT id FROM alumnos WHERE id=? AND curso IN ({}) AND jornada=? AND activo=1'.format(placeholders),
        (aid, *cursos_prof, jornada)).fetchone() is not None
