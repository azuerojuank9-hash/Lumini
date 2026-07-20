def get_alumnos_by_curso(conn, curso_origen, jornada):
    return conn.execute('SELECT id, nombre, curso FROM alumnos WHERE curso=? AND jornada=? AND activo=1', (curso_origen, jornada)).fetchall()

def insert_historial_academico(conn, alumno_id, curso, jornada, promedio, estado, observaciones=None):
    conn.execute(
        'INSERT INTO historial_academico (alumno_id, curso, jornada, promedio_final, estado, observaciones) VALUES (?,?,?,?,?,?)',
        (alumno_id, curso, jornada, promedio, estado, observaciones))

def update_alumno_curso(conn, alumno_id, curso_destino):
    conn.execute('UPDATE alumnos SET curso=? WHERE id=?', (curso_destino, alumno_id))

def get_alumno(conn, alumno_id):
    return conn.execute('SELECT id, nombre, curso, jornada FROM alumnos WHERE id=?', (alumno_id,)).fetchone()

def get_historial_academico(conn, alumno_id):
    return conn.execute('SELECT * FROM historial_academico WHERE alumno_id=? ORDER BY id DESC', (alumno_id,)).fetchall()

def get_all_alumnos(conn):
    return conn.execute('SELECT id, nombre, curso, jornada, activo FROM alumnos ORDER BY curso, nombre').fetchall()

def get_matriculas(conn):
    return conn.execute('SELECT m.*, a.nombre as alumno_nombre FROM matriculas m LEFT JOIN alumnos a ON a.id=m.alumno_id ORDER BY m.created_at DESC').fetchall()

def insert_matricula(conn, nombre, documento, email, telefono, curso_solicitado, jornada, sede):
    conn.execute(
        "INSERT INTO matriculas (nombre, documento, email, telefono, curso_solicitado, jornada, sede, estado) VALUES (?,?,?,?,?,?,?,'pendiente')",
        (nombre, documento, email, telefono, curso_solicitado, jornada, sede))
    conn.commit()

def get_matricula(conn, mid):
    return conn.execute('SELECT * FROM matriculas WHERE id=?', (mid,)).fetchone()

def update_matricula_estado(conn, mid, estado):
    conn.execute('UPDATE matriculas SET estado=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', (estado, mid))

def insert_alumno_desde_matricula(conn, nombre, curso, jornada):
    conn.execute('INSERT INTO alumnos (nombre, curso, jornada, activo) VALUES (?,?,?,1)', (nombre, curso, jornada))
    return conn.execute('SELECT last_insert_rowid() as id').fetchone()['id']

def update_matricula_alumno_id(conn, mid, alumno_id):
    conn.execute('UPDATE matriculas SET alumno_id=? WHERE id=?', (alumno_id, mid))

def get_cupos_por_curso(conn):
    return conn.execute('SELECT curso, jornada, COUNT(*) as inscritos FROM alumnos WHERE activo=1 GROUP BY curso, jornada').fetchall()

def get_facturas(conn):
    return conn.execute('SELECT f.*, a.nombre as alumno_nombre FROM tesoreria_facturas f LEFT JOIN alumnos a ON a.id=f.alumno_id ORDER BY f.created_at DESC').fetchall()

def insert_factura(conn, alumno_id, concepto, monto, descuento, fecha_vencimiento):
    conn.execute(
        'INSERT INTO tesoreria_facturas (alumno_id, concepto, monto, descuento, estado, fecha_vencimiento) VALUES (?,?,?,?,?,?)',
        (alumno_id, concepto, monto, descuento, 'pendiente', fecha_vencimiento))
    conn.commit()

def get_factura(conn, fid):
    return conn.execute('SELECT f.*, a.nombre as alumno_nombre FROM tesoreria_facturas f LEFT JOIN alumnos a ON a.id=f.alumno_id WHERE f.id=?', (fid,)).fetchone()

def insert_pago(conn, factura_id, monto, metodo, referencia):
    conn.execute('INSERT INTO tesoreria_pagos (factura_id, monto, metodo, referencia) VALUES (?,?,?,?)',
                 (factura_id, monto, metodo, referencia))

def get_total_pagado(conn, factura_id):
    r = conn.execute('SELECT COALESCE(SUM(monto),0) as total FROM tesoreria_pagos WHERE factura_id=?', (factura_id,)).fetchone()
    return r['total'] if r else 0

def update_factura_pagada(conn, fid):
    conn.execute('UPDATE tesoreria_facturas SET estado="pagado", fecha_pago=date("now") WHERE id=?', (fid,))

def get_tables(conn):
    return conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'schema_%' AND name NOT LIKE 'password_%' ORDER BY name").fetchall()

def get_columns(conn, tabla):
    return conn.execute(f'PRAGMA table_info("{tabla}")').fetchall()

def execute_report(conn, q, params):
    return conn.execute(q, params).fetchall()

def get_rector_by_id(conn, rid):
    return conn.execute('SELECT * FROM rectores WHERE id=? AND activo=1', (rid,)).fetchone()

def get_rectores(conn):
    return conn.execute('SELECT id, nombre, usuario, email, activo, es_principal FROM rectores ORDER BY es_principal DESC, id').fetchall()

def get_cursos_list(conn):
    return [r['curso'] for r in conn.execute('SELECT DISTINCT curso FROM alumnos WHERE activo=1 ORDER BY curso').fetchall()]

def get_jornadas_list(conn):
    return [r['jornada'] for r in conn.execute('SELECT DISTINCT jornada FROM alumnos WHERE activo=1 ORDER BY jornada').fetchall()]

def get_profesores_list(conn):
    return conn.execute('SELECT id, nombre FROM profesores WHERE activo=1 ORDER BY nombre').fetchall()

def get_profesores_paged(conn, page, per_page):
    return [dict(r) for r in conn.execute(
        'SELECT id, nombre, email, activo FROM profesores ORDER BY nombre LIMIT ? OFFSET ?',
        (per_page, (page - 1) * per_page)).fetchall()]

def count_profesores(conn):
    return conn.execute('SELECT COUNT(*) as c FROM profesores').fetchone()['c']

def get_estudiantes_paged(conn, page, per_page):
    return [dict(r) for r in conn.execute(
        '''SELECT id, nombre, curso, jornada FROM alumnos WHERE activo=1
           ORDER BY curso, nombre LIMIT ? OFFSET ?''',
        (per_page, (page - 1) * per_page)).fetchall()]

def count_estudiantes(conn):
    return conn.execute('SELECT COUNT(*) as c FROM alumnos WHERE activo=1').fetchone()['c']

def get_cursos_agrupados(conn):
    return conn.execute(
        '''SELECT curso, jornada, COUNT(*) as total,
                  SUM(CASE WHEN activo=1 THEN 1 ELSE 0 END) as activos
           FROM alumnos GROUP BY curso, jornada ORDER BY curso''').fetchall()

def get_comunicaciones_rector(conn, rector_id, estado_filtro=None):
    if estado_filtro:
        return conn.execute(
            '''SELECT * FROM comunicaciones WHERE rector_id=? AND activo=1 AND estado=?
               ORDER BY fecha_creacion DESC''',
            (rector_id, estado_filtro)).fetchall()
    return conn.execute(
        '''SELECT * FROM comunicaciones WHERE rector_id=? AND activo=1
           ORDER BY fecha_creacion DESC''',
        (rector_id,)).fetchall()

def get_comunicacion(conn, cid, rector_id=None):
    if rector_id:
        return conn.execute(
            'SELECT * FROM comunicaciones WHERE id=? AND rector_id=? AND activo=1',
            (cid, rector_id)).fetchone()
    return conn.execute(
        'SELECT * FROM comunicaciones WHERE id=? AND activo=1', (cid,)).fetchone()

def insert_comunicacion(conn, rector_id, titulo, contenido, dest_tipo, dest_valor, prioridad, estado, fecha_programada, fecha_publicacion):
    return conn.execute(
        '''INSERT INTO comunicaciones (rector_id,titulo,contenido,destinatario_tipo,destinatario_valor,prioridad,estado,fecha_programada,fecha_publicacion)
           VALUES (?,?,?,?,?,?,?,?,?)''',
        (rector_id, titulo, contenido, dest_tipo, dest_valor, prioridad, estado, fecha_programada, fecha_publicacion)).lastrowid

def update_comunicacion(conn, cid, rector_id, titulo, contenido, dest_tipo, dest_valor, prioridad, estado, fecha_programada, fecha_publicacion):
    conn.execute(
        '''UPDATE comunicaciones SET titulo=?,contenido=?,destinatario_tipo=?,destinatario_valor=?,
           prioridad=?,estado=?,fecha_programada=?,fecha_publicacion=?
           WHERE id=? AND rector_id=?''',
        (titulo, contenido, dest_tipo, dest_valor, prioridad, estado, fecha_programada, fecha_publicacion, cid, rector_id))

def publish_comunicacion(conn, cid, rector_id):
    conn.execute(
        '''UPDATE comunicaciones SET estado='publicado',fecha_publicacion=datetime('now','localtime')
           WHERE id=? AND rector_id=? AND activo=1''',
        (cid, rector_id))

def archive_comunicacion(conn, cid, rector_id):
    conn.execute(
        "UPDATE comunicaciones SET estado='archivado' WHERE id=? AND rector_id=? AND activo=1",
        (cid, rector_id))

def delete_comunicacion(conn, cid, rector_id):
    conn.execute('DELETE FROM comunicaciones WHERE id=? AND rector_id=?', (cid, rector_id))
    conn.execute('DELETE FROM comunicaciones_leidas WHERE comunicacion_id=?', (cid,))

def get_solicitudes(conn, slug):
    return conn.execute(
        '''SELECT s.*, a.nombre as alumno_nombre, p.nombre as profesor_nombre,
                  COALESCE(ac.nombre, s.tipo) as actividad_nombre
           FROM solicitudes_modificacion s
           JOIN alumnos a ON a.id=s.aid
           LEFT JOIN actividades ac ON ac.id=s.actividad_id
           JOIN profesores p ON p.id=s.profesor_id
           WHERE s.slug=?
           ORDER BY s.fecha_solicitud DESC''', (slug,)).fetchall()

def get_solicitud(conn, sid, slug):
    return conn.execute(
        'SELECT * FROM solicitudes_modificacion WHERE id=? AND slug=?', (sid, slug)).fetchone()

def get_canales_list(conn, slug):
    return conn.execute('SELECT * FROM canales WHERE slug=? ORDER BY fecha_creacion DESC', (slug,)).fetchall()

def get_materias_list(conn):
    rows = conn.execute('SELECT DISTINCT materia FROM actividades').fetchall()
    if not rows:
        rows = conn.execute('SELECT DISTINCT materia FROM asignaciones_materia').fetchall()
    return list(set(r['materia'] for r in rows))

def get_auditoria_logs(conn, tabla=None, page=1, limit=50):
    offset = (page - 1) * limit
    where = []
    params = []
    if tabla:
        where.append('a.tabla = ?')
        params.append(tabla)
    where_clause = ('WHERE ' + ' AND '.join(where)) if where else ''
    total = conn.execute(f'SELECT COUNT(*) as c FROM audit_log a {where_clause}', params).fetchone()['c']
    registros = conn.execute(f'''
        SELECT a.*, u.nombre as usuario_nombre
        FROM audit_log a
        LEFT JOIN usuarios u ON a.usuario_id = u.id
        {where_clause}
        ORDER BY a.creado DESC LIMIT ? OFFSET ?
    ''', params + [limit, offset]).fetchall()
    tablas = [r['tabla'] for r in conn.execute(
        "SELECT DISTINCT tabla FROM audit_log ORDER BY tabla"
    ).fetchall()]
    return registros, tablas, total

def get_horarios_curso(conn, curso, jornada):
    return conn.execute(
        'SELECT dia, franja, num, materia, profesor FROM horarios_curso WHERE curso=? AND jornada=?',
        (curso, jornada)).fetchall()

def get_estudiantes_por_curso(conn, curso, jornada=None):
    where = 'a.activo=1'
    params = []
    if curso:
        where += ' AND a.curso=?'; params.append(curso)
    if jornada:
        where += ' AND a.jornada=?'; params.append(jornada)
    return conn.execute(
        f'SELECT a.id, a.nombre, a.num_curso, a.curso, a.jornada FROM alumnos a WHERE {where} ORDER BY a.curso, a.nombre',
        params).fetchall()

def get_estudiantes_search(conn, q):
    return conn.execute('''
        SELECT a.id, a.nombre, a.curso
        FROM alumnos a
        WHERE a.nombre LIKE ?
        ORDER BY a.nombre LIMIT 15
    ''', (f'%{q}%',)).fetchall()

def get_estudiantes_por_curso_simple(conn, curso):
    return conn.execute('SELECT a.id, a.nombre, a.curso FROM alumnos a WHERE a.curso=? AND a.activo=1 ORDER BY a.nombre', (curso,)).fetchall()

def get_observaciones_alumno(conn, aid, slug):
    return conn.execute('''
        SELECT o.*, CASE o.tipo
            WHEN 'positivo' THEN 'Positivo'
            WHEN 'llamado' THEN 'Llamado de atención'
            WHEN 'compromiso' THEN 'Compromiso'
            WHEN 'seguimiento' THEN 'Seguimiento'
        END AS tipo_label
        FROM observador_registros o
        WHERE o.aid=? AND o.slug=?
        ORDER BY o.fecha DESC LIMIT 50
    ''', (aid, slug)).fetchall()

def insert_observacion_observador(conn, slug, aid, tipo, texto, docente):
    conn.execute('''INSERT INTO observador_registros (slug, aid, tipo, texto, docente, estado)
                    VALUES (?,?,?,?,?,?)''',
                 (slug, aid, tipo, texto, docente, 'pendiente'))

def get_expediente_alumno(conn, aid):
    return conn.execute('SELECT * FROM alumnos WHERE id=?', (aid,)).fetchone()

def get_notas_por_materia(conn, aid):
    return {r['materia']: {'promedio': r['promedio'], 'evaluaciones': r['evaluaciones']} for r in conn.execute('''
        SELECT a.materia,
               ROUND(AVG(n.val), 1) AS promedio,
               COUNT(n.id) AS evaluaciones
        FROM notas n
        JOIN actividades a ON a.id = n.actividad_id
        WHERE n.aid=?
        GROUP BY a.materia ORDER BY promedio DESC
    ''', (aid,)).fetchall()}

def get_asistencia_alumno(conn, aid, limit=20):
    return conn.execute('''
        SELECT fecha, estado, observacion FROM asistencia WHERE aid=? ORDER BY fecha DESC LIMIT ?
    ''', (aid, limit)).fetchall()

def get_observador_alumno(conn, aid):
    return conn.execute('''
        SELECT o.*
        FROM observador_registros o
        WHERE o.aid=?
        ORDER BY o.fecha DESC LIMIT 50
    ''', (aid,)).fetchall()

def get_config_institucion(conn, slug):
    return conn.execute('SELECT * FROM config_institucion WHERE slug=?', (slug,)).fetchone()

def get_periodos_estado(conn):
    return conn.execute('SELECT * FROM periodos_estado ORDER BY periodo').fetchall()

def toggle_periodo(conn, periodo, accion, rector_id, now):
    if accion == 'cerrar':
        conn.execute('''INSERT INTO periodos_estado (periodo, estado, fecha_cierre, cerrado_por)
                        VALUES (?, 'cerrado', ?, ?)
                        ON CONFLICT(periodo) DO UPDATE SET estado='cerrado', fecha_cierre=?, cerrado_por=?''',
                     (periodo, now, rector_id, now, rector_id))
    else:
        conn.execute('''INSERT INTO periodos_estado (periodo, estado, fecha_apertura, abierto_por)
                        VALUES (?, 'abierto', ?, ?)
                        ON CONFLICT(periodo) DO UPDATE SET estado='abierto', fecha_apertura=?, abierto_por=?''',
                     (periodo, now, rector_id, now, rector_id))

def count_notificaciones(conn, tipo, uid):
    return conn.execute(
        'SELECT COUNT(*) as c FROM notificaciones WHERE usuario_tipo=? AND usuario_id=? AND leida=0',
        (tipo, uid)).fetchone()['c']

def get_audit_log_recent(conn, limit=8):
    return conn.execute('''SELECT accion, tabla, creado
       FROM audit_log ORDER BY creado DESC LIMIT ?''', (limit,)).fetchall()

def get_ultimos_estudiantes(conn, limit=5):
    return conn.execute('''SELECT id, nombre, curso, jornada FROM alumnos
       WHERE activo=1 ORDER BY id DESC LIMIT ?''', (limit,)).fetchall()

def get_ultimos_profesores(conn, limit=5):
    return conn.execute('''SELECT id, nombre, email FROM profesores
       WHERE activo=1 ORDER BY id DESC LIMIT ?''', (limit,)).fetchall()

def get_proximos_eventos(conn, hoy, limit=5):
    return conn.execute('''SELECT titulo, fecha, materia, curso, jornada
       FROM compromisos WHERE fecha >= ?
       ORDER BY fecha LIMIT ?''', (hoy, limit)).fetchall()

def get_actividad_reciente(conn, limit=6):
    return conn.execute('''SELECT accion, tabla, creado
       FROM audit_log ORDER BY creado DESC LIMIT ?''', (limit,)).fetchall()

def get_profesores_con_materias(conn, curso, jornada, periodo):
    return conn.execute('''
        SELECT DISTINCT am.materia, p.nombre,
           (SELECT COUNT(*) FROM actividades a
            WHERE a.profesor_id=p.id AND a.curso=? AND a.jornada=?
            AND COALESCE(a.periodo,1)=?) as cnt
           FROM profesores p
           JOIN asignaciones_curso ac ON ac.profesor_id=p.id
           JOIN asignaciones_materia am ON am.profesor_id=p.id AND am.jornada=ac.jornada AND am.materia=ac.materia
           WHERE ac.curso=? AND ac.jornada=? AND p.activo=1''',
        (curso, jornada, periodo, curso, jornada)).fetchall()

def update_rector(conn, rid, nombre, email, password_hash=None):
    if password_hash:
        conn.execute('UPDATE rectores SET nombre=?, email=?, password=? WHERE id=?',
                     (nombre, email, password_hash, rid))
    else:
        conn.execute('UPDATE rectores SET nombre=?, email=? WHERE id=?',
                     (nombre, email, rid))

def update_rector_perfil_full(conn, rid, nombre, email, password_hash):
    conn.execute('UPDATE rectores SET nombre=?, email=?, password=? WHERE id=?',
                 (nombre, email, password_hash, rid))

def update_rector_perfil(conn, rid, nombre, email):
    conn.execute('UPDATE rectores SET nombre=?, email=? WHERE id=?',
                 (nombre, email, rid))

def insert_rector(conn, nombre, usuario, password_hash, email=''):
    conn.execute(
        'INSERT INTO rectores (nombre, usuario, password, email) VALUES (?, ?, ?, ?)',
        (nombre, usuario, password_hash, email))

def delete_rector(conn, rid):
    conn.execute('DELETE FROM rectores WHERE id=?', (rid,))

def set_rector_principal(conn, rid, val):
    conn.execute('UPDATE rectores SET es_principal=? WHERE id=?', (val, rid))

def get_rector_por_usuario(conn, usuario):
    return conn.execute('SELECT 1 FROM rectores WHERE usuario=?', (usuario,)).fetchone()

def get_rector_por_usuario_excluir(conn, usuario, rid):
    return conn.execute('SELECT 1 FROM rectores WHERE usuario=? AND id!=?', (usuario, rid)).fetchone()

def get_canales(conn, slug):
    return conn.execute('SELECT * FROM canales WHERE slug=? ORDER BY fecha_creacion DESC', (slug,)).fetchall()

def insert_canal(conn, slug, rector_id, tipo, nombre, descripcion, curso, materia):
    return conn.execute('INSERT INTO canales (slug,rector_id,tipo,nombre,descripcion,curso,materia) VALUES (?,?,?,?,?,?,?)',
                        (slug, rector_id, tipo, nombre, descripcion, curso, materia)).lastrowid

def soft_delete_canal(conn, cid, slug):
    conn.execute('UPDATE canales SET activo=0 WHERE id=? AND slug=?', (cid, slug))

def get_canal(conn, cid):
    return conn.execute('SELECT * FROM canales WHERE id=?', (cid,)).fetchone()

def get_canal_miembros(conn, cid):
    return conn.execute('SELECT * FROM canal_miembros WHERE canal_id=?', (cid,)).fetchall()

def get_alumnos_activos_por_filtro(conn, curso, jornada):
    where = 'a.activo=1'
    params = []
    if curso:
        where += ' AND a.curso=?'; params.append(curso)
    if jornada:
        where += ' AND a.jornada=?'; params.append(jornada)
    return conn.execute(
        f'SELECT a.id, a.nombre, a.num_curso, a.curso, a.jornada FROM alumnos a WHERE {where} ORDER BY a.curso, a.nombre',
        params).fetchall()

def get_asistencia_por_fecha(conn, fecha, aids):
    ph = ','.join('?' * len(aids))
    return conn.execute(
        f'SELECT aid, estado, observacion, hora FROM asistencia WHERE fecha=? AND aid IN ({ph})',
        (fecha,) + tuple(aids)).fetchall()
