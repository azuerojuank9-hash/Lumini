from app import repositories as repo

def dashboard_data(rector, conn, slug):
    colegio_config = repo.get_config_institucion(conn, slug)
    total_alumnos = len(repo.get_all_alumnos(conn))
    total_profesores = repo.count_profesores(conn)
    total_matriculas = len(repo.get_matriculas(conn))
    pendientes = repo.count_notificaciones(conn, 'rector', rector.get('id', 0))
    audit_recent = [dict(r) for r in repo.get_audit_log_recent(conn)]
    ult_estudiantes = [dict(r) for r in repo.get_ultimos_estudiantes(conn)]
    ult_profesores = [dict(r) for r in repo.get_ultimos_profesores(conn)]
    from datetime import date
    hoy = date.today().isoformat()
    prox_eventos = [dict(r) for r in repo.get_proximos_eventos(conn, hoy)]
    actividad_reciente = [dict(r) for r in repo.get_actividad_reciente(conn)]
    return {
        'colegio': colegio_config,
        'total_alumnos': total_alumnos,
        'total_profesores': total_profesores,
        'total_matriculas': total_matriculas,
        'pendientes': pendientes,
        'audit_recent': audit_recent,
        'ultimos_estudiantes': ult_estudiantes,
        'ultimos_profesores': ult_profesores,
        'proximos_eventos': prox_eventos,
        'actividad_reciente': actividad_reciente,
    }

def horarios_curso_data(conn, curso, jornada):
    horarios = repo.get_horarios_curso(conn, curso, jornada)
    horarios_por_dia = {}
    for h in horarios:
        dia = h['dia']
        if dia not in horarios_por_dia:
            horarios_por_dia[dia] = []
        horarios_por_dia[dia].append(dict(h))
    estudiantes = repo.get_estudiantes_por_curso(conn, curso, jornada)
    return horarios_por_dia, estudiantes

def save_horarios(conn, curso, jornada, horarios_data):
    conn.execute('DELETE FROM horarios_curso WHERE curso=? AND jornada=?', (curso, jornada))
    for h in horarios_data:
        conn.execute('INSERT INTO horarios_curso (dia, franja, num, materia, profesor, curso, jornada) VALUES (?,?,?,?,?,?,?)',
                     (h['dia'], h['franja'], h['num'], h['materia'], h['profesor'], curso, jornada))

def profesores_paged(conn, page, per_page):
    return [dict(r) for r in repo.get_profesores_paged(conn, page, per_page)]

def count_profesores(conn):
    return repo.count_profesores(conn)

def estudiantes_paged(conn, page, per_page):
    return [dict(r) for r in repo.get_estudiantes_paged(conn, page, per_page)]

def count_estudiantes(conn):
    return repo.count_estudiantes(conn)

def cursos_data(conn):
    return [dict(r) for r in repo.get_cursos_agrupados(conn)]

def matricular(conn, nombre, documento, email, telefono, curso_solicitado, jornada, sede):
    repo.insert_matricula(conn, nombre, documento, email, telefono, curso_solicitado, jornada, sede)

def aprobar_matricula(conn, mid):
    mat = repo.get_matricula(conn, mid)
    if mat:
        repo.update_matricula_estado(conn, mid, 'aprobado')
        alumno_id = repo.insert_alumno_desde_matricula(conn, mat['nombre'], mat['curso_solicitado'], mat['jornada'])
        repo.update_matricula_alumno_id(conn, mid, alumno_id['id'])
        conn.commit()

def rechazar_matricula(conn, mid):
    repo.update_matricula_estado(conn, mid, 'rechazado')
    conn.commit()

def facturar(conn, alumno_id, concepto, monto, descuento, fecha_vencimiento):
    repo.insert_factura(conn, alumno_id, concepto, monto, descuento, fecha_vencimiento)

def registrar_pago(conn, factura_id, monto, metodo, referencia, conn_commit):
    repo.insert_pago(conn, factura_id, monto, metodo, referencia)
    total = repo.get_total_pagado(conn, factura_id)
    fact = repo.get_factura(conn, factura_id)
    if total >= fact['monto']:
        repo.update_factura_pagada(conn, factura_id)
    conn.commit()

def reporte_ejecutar(conn, consulta, params):
    return repo.execute_report(conn, consulta, params)

def estudiante_detail(conn, aid, slug):
    alumno = repo.get_expediente_alumno(conn, aid)
    materias = repo.get_notas_por_materia(conn, aid)
    asistencia = repo.get_asistencia_alumno(conn, aid)
    observador = repo.get_observador_alumno(conn, aid)
    observaciones = repo.get_observaciones_alumno(conn, aid, slug)
    historial = repo.get_historial_academico(conn, aid)
    return {
        'alumno': alumno,
        'materias': materias,
        'asistencia': asistencia,
        'observador': observador,
        'observaciones': observaciones,
        'historial': historial,
    }

def get_comunicaciones(rector_id, conn, estado=None):
    return [dict(r) for r in repo.get_comunicaciones_rector(conn, rector_id, estado)]

def crear_comunicacion(conn, rector_id, data):
    return repo.insert_comunicacion(conn, data.get('destinatario'), data.get('tipo') or 'papelera',
        rector_id,
        data['titulo'], data['contenido'],
        data['destinatario_tipo'], data.get('destinatario_valor', ''),
        data['prioridad'], data['estado'],
        data.get('fecha_programada'), data.get('fecha_publicacion'))

def editar_comunicacion(conn, cid, rector_id, data):
    repo.update_comunicacion(conn, cid, rector_id,
        data['titulo'], data['contenido'],
        data['destinatario_tipo'], data.get('destinatario_valor', ''),
        data['prioridad'], data['estado'],
        data.get('fecha_programada'), data.get('fecha_publicacion'))

def publicar_comunicacion(conn, cid, rector_id):
    repo.publish_comunicacion(conn, cid, rector_id)

def archivar_comunicacion(conn, cid, rector_id):
    repo.archive_comunicacion(conn, cid, rector_id)

def eliminar_comunicacion(conn, cid, rector_id):
    repo.delete_comunicacion(conn, cid, rector_id)

def get_solicitudes_list(conn, slug):
    return [dict(r) for r in repo.get_solicitudes(conn, slug)]

def get_auditoria(conn, tabla=None, page=1, limit=50):
    registros, tablas, total = repo.get_auditoria_logs(conn, tabla, page, limit)
    return {'registros': [dict(r) for r in registros], 'tablas': tablas, 'total': total}

def gestion_rectores_list(conn):
    return [dict(r) for r in repo.get_rectores(conn)]

def crear_rector(conn, nombre, usuario, password_hash, email):
    repo.insert_rector(conn, nombre, usuario, password_hash, email)
    conn.commit()

def editar_rector(conn, rid, nombre, email, password_hash=None):
    repo.update_rector(conn, rid, nombre, email, password_hash)
    conn.commit()

def eliminar_rector(conn, rid):
    repo.delete_rector(conn, rid)
    conn.commit()

def alternar_principal(conn, rid):
    r = repo.get_rector_by_id(conn, rid)
    if r:
        repo.set_rector_principal(conn, rid, 0 if r.get('es_principal') else 1)
        conn.commit()
