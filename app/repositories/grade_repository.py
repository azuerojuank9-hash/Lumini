from app.models.schema import conectar


def find_actividad_by_id(slug, act_id):
    conn = conectar(slug)
    try:
        return conn.execute('SELECT * FROM actividades WHERE id=?', (act_id,)).fetchone()
    finally:
        conn.close()


def find_actividad_by_id_and_profesor(slug, act_id, profesor_id):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT * FROM actividades WHERE id=? AND profesor_id=?', (act_id, profesor_id)
        ).fetchone()
    finally:
        conn.close()


def get_max_orden_actividad(slug, profesor_id, materia, jornada, curso, periodo):
    conn = conectar(slug)
    try:
        return conn.execute(
            '''SELECT COALESCE(MAX(orden),0) FROM actividades
               WHERE profesor_id=? AND materia=? AND jornada=? AND curso=?
               AND COALESCE(periodo,1)=?''',
            (profesor_id, materia, jornada, curso, periodo)
        ).fetchone()[0]
    finally:
        conn.close()


def create_actividad(slug, profesor_id, materia, jornada, curso, nombre, orden, periodo,
                     tipo='taller', peso=None, fecha_limite=None, hora_limite=None,
                     descripcion=None, observaciones=None, estado_act='borrador',
                     competencia=None, entrega_digital=0):
    conn = conectar(slug)
    try:
        c = conn.execute(
            '''INSERT INTO actividades
               (profesor_id,materia,jornada,curso,nombre,orden,periodo,tipo,peso,fecha_limite,
                hora_limite,descripcion,observaciones,estado_act,competencia,entrega_digital)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (profesor_id, materia, jornada, curso, nombre, orden, periodo,
             tipo, peso, fecha_limite, hora_limite, descripcion,
             observaciones, estado_act, competencia, entrega_digital))
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def update_actividad_field(slug, act_id, field, value):
    ALLOWED_FIELDS = {'nombre', 'descripcion', 'fecha', 'peso', 'periodo', 'tipo'}
    if field not in ALLOWED_FIELDS:
        return False
    conn = conectar(slug)
    try:
        conn.execute(f'UPDATE actividades SET {field}=? WHERE id=?', (value, act_id))
        conn.commit()
    finally:
        conn.close()


def delete_actividad_and_notas(slug, act_id):
    conn = conectar(slug)
    try:
        notas = conn.execute('SELECT aid, val FROM notas WHERE actividad_id=?', (act_id,)).fetchall()
        conn.execute('DELETE FROM notas WHERE actividad_id=?', (act_id,))
        conn.execute('DELETE FROM actividades WHERE id=?', (act_id,))
        conn.commit()
        return notas
    finally:
        conn.close()


def get_actividades_by_curso(slug, profesor_id, materia, jornada, curso, periodo):
    conn = conectar(slug)
    try:
        return conn.execute(
            '''SELECT * FROM actividades
               WHERE profesor_id=? AND materia=? AND jornada=? AND curso=?
               AND COALESCE(periodo,1)=? ORDER BY orden''',
            (profesor_id, materia, jornada, curso, periodo)
        ).fetchall()
    finally:
        conn.close()


def get_alumnos_by_curso(slug, curso, jornada):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT * FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre COLLATE NOCASE',
            (curso, jornada)
        ).fetchall()
    finally:
        conn.close()


def get_notas_by_actividad(slug, act_id):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT aid, val FROM notas WHERE actividad_id=?', (act_id,)
        ).fetchall()
    finally:
        conn.close()


def get_nota(slug, aid, actividad_id):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT val FROM notas WHERE aid=? AND actividad_id=?',
            (aid, actividad_id)
        ).fetchone()
    finally:
        conn.close()


def upsert_nota(slug, aid, actividad_id, val):
    conn = conectar(slug)
    try:
        conn.execute(
            '''INSERT INTO notas (aid,actividad_id,val) VALUES (?,?,?)
               ON CONFLICT(aid,actividad_id) DO UPDATE SET val=excluded.val''',
            (aid, actividad_id, val))
        conn.commit()
    finally:
        conn.close()


def delete_nota(slug, aid, actividad_id):
    conn = conectar(slug)
    try:
        conn.execute('DELETE FROM notas WHERE aid=? AND actividad_id=?', (aid, actividad_id))
        conn.commit()
    finally:
        conn.close()


def get_evaluacion(slug, aid, profesor_id, materia, jornada, periodo):
    conn = conectar(slug)
    try:
        return conn.execute(
            '''SELECT evaluacion, autoevaluacion FROM evaluaciones
               WHERE aid=? AND profesor_id=? AND materia=? AND jornada=? AND COALESCE(periodo,1)=?''',
            (aid, profesor_id, materia, jornada, periodo)
        ).fetchone()
    finally:
        conn.close()


def upsert_evaluacion(slug, aid, profesor_id, materia, jornada, evaluacion, autoevaluacion, periodo):
    conn = conectar(slug)
    try:
        conn.execute(
            '''INSERT INTO evaluaciones
               (aid,profesor_id,materia,jornada,evaluacion,autoevaluacion,periodo)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(aid,profesor_id,materia,jornada,periodo)
               DO UPDATE SET evaluacion=excluded.evaluacion, autoevaluacion=excluded.autoevaluacion''',
            (aid, profesor_id, materia, jornada, evaluacion, autoevaluacion, periodo))
        conn.commit()
    finally:
        conn.close()


def get_notas_for_student(slug, aid, materia, jornada, curso, periodo, profesor_id):
    conn = conectar(slug)
    try:
        return conn.execute(
            '''SELECT n.val FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
               WHERE n.aid=? AND ac.materia=? AND ac.jornada=? AND ac.curso=?
               AND COALESCE(ac.periodo,1)=? AND ac.profesor_id=?''',
            (aid, materia, jornada, curso, periodo, profesor_id)
        ).fetchall()
    finally:
        conn.close()


def get_all_notas_for_curso(slug, aid_list, materia, jornada, curso, periodo, profesor_id):
    conn = conectar(slug)
    try:
        placeholders = ','.join('?' * len(aid_list))
        return conn.execute(
            f'''SELECT n.aid, n.actividad_id, n.val, n.id FROM notas n
                JOIN actividades ac ON ac.id=n.actividad_id
                WHERE n.aid IN ({placeholders}) AND ac.materia=? AND ac.jornada=? AND ac.curso=?
                AND COALESCE(ac.periodo,1)=? AND ac.profesor_id=? ORDER BY n.aid''',
            (*aid_list, materia, jornada, curso, periodo, profesor_id)
        ).fetchall()
    finally:
        conn.close()


def get_all_evaluaciones_for_curso(slug, aid_list, profesor_id, materia, jornada, periodo):
    conn = conectar(slug)
    try:
        placeholders = ','.join('?' * len(aid_list))
        return conn.execute(
            f'''SELECT aid, evaluacion, autoevaluacion FROM evaluaciones
                WHERE aid IN ({placeholders}) AND profesor_id=? AND materia=? AND jornada=?
                AND COALESCE(periodo,1)=?''',
            (*aid_list, profesor_id, materia, jornada, periodo)
        ).fetchall()
    finally:
        conn.close()


def get_historial_notas_estudiante(slug, aid):
    conn = conectar(slug)
    try:
        return conn.execute(
            '''SELECT a.id, a.tipo_accion, a.tabla, a.campo, a.valor_anterior, a.valor_nuevo,
                      a.creado, a.materia, a.periodo, a.motivo, a.aid,
                      COALESCE(ac.nombre, '') as actividad_nombre
               FROM auditoria_notas a
               LEFT JOIN actividades ac ON ac.id = a.actividad_id
               WHERE a.aid = ?
               ORDER BY a.creado DESC
               LIMIT 200''',
            (aid,)
        ).fetchall()
    finally:
        conn.close()


def get_historial_notas_curso(slug, curso, materia, periodo, profesor_id):
    conn = conectar(slug)
    try:
        return conn.execute(
            '''SELECT a.id, a.tipo_accion, a.tabla, a.campo, a.valor_anterior, a.valor_nuevo,
                      a.creado, a.materia, a.periodo, a.motivo, a.aid,
                      COALESCE(ac.nombre, '') as actividad_nombre
               FROM auditoria_notas a
               LEFT JOIN actividades ac ON ac.id = a.actividad_id
               WHERE a.curso = ? AND a.materia = ? AND a.periodo = ? AND a.profesor_id = ?
               ORDER BY a.creado DESC
               LIMIT 500''',
            (curso, materia, periodo, profesor_id)
        ).fetchall()
    finally:
        conn.close()


def get_alumno_by_id(slug, aid):
    conn = conectar(slug)
    try:
        return conn.execute('SELECT * FROM alumnos WHERE id=?', (aid,)).fetchone()
    finally:
        conn.close()


def get_curso_alumno(slug, aid):
    conn = conectar(slug)
    try:
        return conn.execute('SELECT curso FROM alumnos WHERE id=?', (aid,)).fetchone()
    finally:
        conn.close()


def count_alumnos_curso(slug, curso, jornada):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT COUNT(*) as c FROM alumnos WHERE curso=? AND jornada=? AND activo=1',
            (curso, jornada)
        ).fetchone()['c']
    finally:
        conn.close()


def get_actividades_count(slug, materia, jornada, curso, periodo, profesor_id):
    conn = conectar(slug)
    try:
        return len(conn.execute(
            '''SELECT id FROM actividades WHERE materia=? AND jornada=? AND curso=?
               AND COALESCE(periodo,1)=? AND profesor_id=?''',
            (materia, jornada, curso, periodo, profesor_id)
        ).fetchall())
    finally:
        conn.close()


def get_notas_count(slug, materia, jornada, curso, periodo, profesor_id):
    conn = conectar(slug)
    try:
        return conn.execute(
            '''SELECT COUNT(*) as c FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
               WHERE ac.materia=? AND ac.jornada=? AND ac.curso=? AND COALESCE(ac.periodo,1)=?
               AND ac.profesor_id=?''',
            (materia, jornada, curso, periodo, profesor_id)
        ).fetchone()['c']
    finally:
        conn.close()


def get_cursos_distinct(slug, materia, jornada, profesor_id):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT DISTINCT curso FROM actividades WHERE materia=? AND jornada=? AND profesor_id=? ORDER BY curso',
            (materia, jornada, profesor_id)
        ).fetchall()
    finally:
        conn.close()


def create_solicitud_modificacion(slug, datos):
    conn = conectar(slug)
    try:
        conn.execute(
            '''INSERT INTO solicitudes_modificacion
               (slug, aid, profesor_id, materia, curso, jornada, periodo, tipo, actividad_id,
                valor_actual, valor_solicitado, motivo, estado)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'pendiente')''',
            datos
        )
        conn.commit()
        return conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    finally:
        conn.close()


def create_observacion(slug, aid, materia, texto):
    conn = conectar(slug)
    try:
        conn.execute(
            'INSERT INTO observaciones (aid, materia, texto, fecha) VALUES (?,?,?,date("now"))',
            (aid, materia, texto))
        conn.commit()
    finally:
        conn.close()


def get_observaciones_by_aid(slug, aid):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT id, materia, texto, fecha FROM observaciones WHERE aid=? ORDER BY fecha DESC LIMIT 20',
            (aid,)
        ).fetchall()
    finally:
        conn.close()


def get_actividades_by_profesor_materia_jornada(slug, profesor_id, materia, jornada):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT id, nombre, tipo, peso, fecha_limite, estado_act FROM actividades '
            'WHERE materia=? AND jornada=? AND profesor_id=? ORDER BY orden',
            (materia, jornada, profesor_id)
        ).fetchall()
    finally:
        conn.close()


def get_notas_stats_actividad(slug, act_id):
    conn = conectar(slug)
    try:
        vals = [float(r['val']) for r in conn.execute(
            'SELECT val FROM notas WHERE actividad_id=? AND val IS NOT NULL', (act_id,)
        ).fetchall()]
        return vals
    finally:
        conn.close()
