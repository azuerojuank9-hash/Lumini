import json
import logging
from datetime import datetime

from flask import Response

from app.routes import rector_bp
from app.services.channel_service import nombre_usuario_canal as _nombre_usuario_canal
from app.services.excel_service import (
    extension_excel_valida,
    leer_workbook,
    wb_desde_filas,
    xlsx_bytes,
)

logger = logging.getLogger(__name__)

MIME_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

# Allow-list de tablas/columnas para reportes (evita inyección SQL).
COLUMNAS_REPORTES = {
    'alumnos': [{'name': 'id', 'type': 'INTEGER'}, {'name': 'nombre', 'type': 'TEXT'},
                {'name': 'curso', 'type': 'TEXT'}, {'name': 'jornada', 'type': 'TEXT'},
                {'name': 'documento', 'type': 'TEXT'}, {'name': 'activo', 'type': 'INTEGER'}],
    'profesores': [{'name': 'id', 'type': 'INTEGER'}, {'name': 'nombre', 'type': 'TEXT'},
                   {'name': 'usuario', 'type': 'TEXT'}, {'name': 'email', 'type': 'TEXT'},
                   {'name': 'activo', 'type': 'INTEGER'}],
    'asignaciones_materia': [{'name': 'id', 'type': 'INTEGER'},
                             {'name': 'profesor_id', 'type': 'INTEGER'},
                             {'name': 'materia', 'type': 'TEXT'}, {'name': 'jornada', 'type': 'TEXT'}],
    'notas': [{'name': 'id', 'type': 'INTEGER'}, {'name': 'aid', 'type': 'INTEGER'},
              {'name': 'actividad_id', 'type': 'INTEGER'}, {'name': 'val', 'type': 'REAL'}],
    'asistencia': [{'name': 'id', 'type': 'INTEGER'}, {'name': 'aid', 'type': 'INTEGER'},
                   {'name': 'fecha', 'type': 'TEXT'}, {'name': 'estado', 'type': 'TEXT'},
                   {'name': 'observacion', 'type': 'TEXT'}],
    'actividades': [{'name': 'id', 'type': 'INTEGER'}, {'name': 'nombre', 'type': 'TEXT'},
                    {'name': 'materia', 'type': 'TEXT'}, {'name': 'periodo', 'type': 'INTEGER'},
                    {'name': 'curso', 'type': 'TEXT'}],
    'comunicaciones': [{'name': 'id', 'type': 'INTEGER'}, {'name': 'titulo', 'type': 'TEXT'},
                       {'name': 'contenido', 'type': 'TEXT'}, {'name': 'fecha_creacion', 'type': 'TEXT'}],
    'audit_log': [{'name': 'id', 'type': 'INTEGER'}, {'name': 'usuario_id', 'type': 'INTEGER'},
                  {'name': 'accion', 'type': 'TEXT'}, {'name': 'tabla', 'type': 'TEXT'},
                  {'name': 'creado', 'type': 'TEXT'}],
}


def _institucional(fa, slug):
    """Devuelve (rol, usuario) para rector o directora, o (None, None)."""
    rector = fa.get_rector(slug)
    if rector:
        return 'rector', dict(rector)
    directora = fa.get_directora(slug)
    if directora:
        return 'directora', dict(directora)
    return None, None


def _ctx_institucional(fa, rol, usuario):
    """Variables extra que requieren los sidebars (rector o directora)."""
    if rol == 'rector':
        return {'rector': usuario}
    return {'directora': usuario,
            'curso': usuario.get('curso', ''),
            'jornada': usuario.get('jornada', ''),
            'periodo': 1}


def _filtrar_columnas_reportes(tabla, columnas):
    """Valida columnas contra el allow-list. Devuelve (col_names, error)."""
    permitidas = COLUMNAS_REPORTES.get(tabla)
    if not permitidas:
        return None, 'Tabla no permitida.'
    nombres_permitidos = {c['name'] for c in permitidas}
    if columnas:
        if not isinstance(columnas, list) or not columnas:
            return None, 'Columnas inválidas.'
        cols = [c for c in columnas if isinstance(c, str) and c in nombres_permitidos]
        if len(cols) != len(columnas):
            return None, 'Columna no permitida.'
        return cols, None
    return list(nombres_permitidos), None


def _fa():
    import sys
    if 'flask_app' in sys.modules:
        return sys.modules['flask_app']
    import flask_app
    return flask_app


@rector_bp.route('/<slug>/rector')
@rector_bp.route('/<slug>/rector/panel')
def rector_panel(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    conn = fa.conectar(slug)
    total_est = conn.execute('SELECT COUNT(*) as c FROM alumnos WHERE activo=1').fetchone()['c']
    total_prof = conn.execute('SELECT COUNT(*) as c FROM profesores WHERE activo=1').fetchone()['c']
    total_cursos = conn.execute('SELECT DISTINCT curso as c FROM alumnos WHERE activo=1').fetchall()
    total_cursos = len(total_cursos)
    total_materias = conn.execute('SELECT DISTINCT materia as c FROM asignaciones_materia').fetchall()
    total_materias = len(total_materias)
    total_directoras = conn.execute('SELECT COUNT(*) as c FROM directoras WHERE activo=1').fetchone()['c']
    hoy = datetime.today().strftime('%Y-%m-%d')
    asistencia_hoy = conn.execute("SELECT COUNT(DISTINCT aid) as c FROM asistencia WHERE fecha=?", (hoy,)).fetchone()['c']
    comunicaciones = conn.execute('''SELECT * FROM comunicaciones WHERE rector_id=? AND activo=1 ORDER BY fecha_creacion DESC LIMIT 5''', (rector['id'],)).fetchall()
    notif_count = conn.execute('SELECT COUNT(*) as c FROM notificaciones WHERE usuario_tipo=? AND usuario_id=? AND leida=0', ('rector', rector['id'])).fetchone()['c']
    actividad_reciente = conn.execute('''SELECT accion, tabla, creado FROM audit_log ORDER BY creado DESC LIMIT 8''').fetchall()
    actividad_reciente = [dict(r) for r in actividad_reciente]
    ultimos_estudiantes = conn.execute('''SELECT id, nombre, curso, jornada FROM alumnos WHERE activo=1 ORDER BY id DESC LIMIT 5''').fetchall()
    ultimos_estudiantes = [dict(r) for r in ultimos_estudiantes]
    ultimos_profesores = conn.execute('''SELECT id, nombre, email FROM profesores WHERE activo=1 ORDER BY id DESC LIMIT 5''').fetchall()
    ultimos_profesores = [dict(r) for r in ultimos_profesores]
    proximos_eventos = conn.execute('''SELECT titulo, fecha, materia, curso, jornada FROM compromisos WHERE fecha >= ? ORDER BY fecha LIMIT 5''', (hoy,)).fetchall()
    proximos_eventos = [dict(r) for r in proximos_eventos]
    solicitudes_pendientes = conn.execute(
        "SELECT COUNT(*) as c FROM solicitudes_modificacion WHERE estado='pendiente' AND slug=?", (slug,)).fetchone()['c']
    periodos_estado_raw = conn.execute('SELECT * FROM periodos_estado ORDER BY periodo').fetchall()
    periodos_estado = {r['periodo']: dict(r) for r in periodos_estado_raw}
    periodo_actual = 1
    periodo_actual_estado = periodos_estado.get(periodo_actual, {}).get('estado', 'abierto')
    # M4: mismas métricas ponderadas (65/25/10) que el dashboard del rector,
    # con umbrales relativos a la escala del colegio.
    cfg = fa.config_get(slug)
    escala_max = float(cfg.get('escala_max', 5.0))
    nota_min_aprobar = float(cfg.get('nota_minima_aprobar', 3.0))
    if escala_max > 5.0:
        nota_min_aprobar /= 2.0
    notas_all = conn.execute(
        '''SELECT n.aid, n.val, ac.materia, ac.jornada
           FROM notas n JOIN actividades ac ON ac.id = n.actividad_id''').fetchall()
    ev_all = conn.execute(
        'SELECT aid, materia, jornada, evaluacion, autoevaluacion FROM evaluaciones').fetchall()
    notas_idx = {}
    for r in notas_all:
        notas_idx.setdefault((r['aid'], r['materia'], r['jornada']), []).append(r['val'])
    ev_idx = {}
    for r in ev_all:
        ev_idx[(r['aid'], r['materia'], r['jornada'])] = r
    subj_final = {}
    for key in set(notas_idx) | set(ev_idx):
        ev = ev_idx.get(key)
        ev_v = ev['evaluacion'] if ev and ev['evaluacion'] is not None else None
        au_v = ev['autoevaluacion'] if ev and ev['autoevaluacion'] is not None else None
        final = fa._promedio_ponderado(notas_idx.get(key, []), ev_v, au_v)
        if final is not None:
            subj_final[key] = final
    student_overall = {}
    for (aid, _m, _j), final in subj_final.items():
        student_overall.setdefault(aid, []).append(final)
    student_overall = {aid: round(sum(v) / len(v), 2) for aid, v in student_overall.items()}
    all_finals = list(student_overall.values())
    prom_inst = round(sum(all_finals) / len(all_finals), 2) if all_finals else None
    promedio_institucional = prom_inst
    # Alumnos de bajo rendimiento (ponderado y escala-aware).
    bajo_rows = []
    for aid, avg in sorted(student_overall.items(), key=lambda x: x[1]):
        if avg < nota_min_aprobar:
            a = conn.execute('SELECT id, nombre, curso, jornada FROM alumnos WHERE id=? AND activo=1', (aid,)).fetchone()
            if a:
                bajo_rows.append({'nombre': a['nombre'], 'promedio': avg, 'curso': a['curso']})
            if len(bajo_rows) >= 5:
                break
    bajo_rendimiento = bajo_rows
    # Promedio por curso (ponderado por estudiante).
    curso_avgs = {}
    for a in conn.execute('SELECT id, curso FROM alumnos WHERE activo=1').fetchall():
        avg = student_overall.get(a['id'])
        if avg is not None:
            curso_avgs.setdefault(a['curso'], []).append(avg)
    promedio_por_curso = [{'curso': k, 'promedio': round(sum(v) / len(v), 2)}
                          for k, v in sorted(curso_avgs.items())]
    # Distribución por alumno con umbrales relativos a la escala.
    step = (escala_max / 5.0) * 0.5
    dist = {'bajo': 0, 'medio': 0, 'alto': 0, 'sobresaliente': 0}
    for p in all_finals:
        if p < nota_min_aprobar:
            dist['bajo'] += 1
        elif p < nota_min_aprobar + step:
            dist['medio'] += 1
        elif p < nota_min_aprobar + 2 * step:
            dist['alto'] += 1
        else:
            dist['sobresaliente'] += 1
    distribucion = [
        {'label': 'Bajo (<%.1f)' % nota_min_aprobar, 'count': dist['bajo']},
        {'label': 'Medio (%.1f\u2013%.1f)' % (nota_min_aprobar, round(nota_min_aprobar + step - 0.05, 1)), 'count': dist['medio']},
        {'label': 'Alto (%.1f\u2013%.1f)' % (round(nota_min_aprobar + step, 1), round(nota_min_aprobar + 2 * step - 0.05, 1)), 'count': dist['alto']},
        {'label': 'Sobresaliente (\u2265%.1f)' % round(nota_min_aprobar + 2 * step, 1), 'count': dist['sobresaliente']},
    ]
    conn.close()
    return fa.render_template('rector_panel.html',
                           slug=slug, colegio=colegio, rector=rector,
                           total_estudiantes=total_est,
                           total_profesores=total_prof,
                           total_cursos=total_cursos,
                           total_materias=total_materias,
                           total_directoras=total_directoras,
                           asistencia_hoy=asistencia_hoy,
                           comunicaciones=comunicaciones,
                           notif_count=notif_count,
                           actividad_reciente=actividad_reciente,
                           ultimos_estudiantes=ultimos_estudiantes,
                           ultimos_profesores=ultimos_profesores,
                           proximos_eventos=proximos_eventos,
                           solicitudes_pendientes=solicitudes_pendientes,
                           periodo_actual=periodo_actual,
                           periodo_actual_estado=periodo_actual_estado,
                           promedio_institucional=promedio_institucional,
                           bajo_rendimiento=bajo_rendimiento,
                           promedio_por_curso=promedio_por_curso,
                           distribucion=distribucion,
                           escala_max=escala_max)


@rector_bp.route('/<slug>/rector/horarios')
def rector_horarios(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    conn = fa.conectar(slug)
    cursos = [r['curso'] for r in conn.execute('SELECT DISTINCT curso FROM alumnos WHERE activo=1 ORDER BY curso').fetchall()]
    jornadas = fa.JORNADAS
    conn.close()
    return fa.render_template('rector_horarios.html',
                           slug=slug, colegio=colegio, rector=rector,
                           cursos=cursos, jornadas=jornadas,
                           notif_count=fa.notificaciones_no_leidas(slug, 'rector', rector['id']))


@rector_bp.route('/<slug>/rector/horarios/datos')
def rector_horarios_datos(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.jsonify({})
    curso = fa.request.args.get('curso', '')
    jornada = fa.request.args.get('jornada', '')
    if not curso:
        return fa.jsonify({})
    conn = fa.conectar(slug)
    filas = conn.execute('SELECT dia, franja, num, materia, profesor FROM horarios_curso WHERE curso=? AND jornada=?',
                         (curso, jornada)).fetchall()
    conn.close()
    mapa = {}
    for r in filas:
        mapa[f"{r['dia']}_{r['franja']}"] = {'num': r['num'], 'materia': r['materia'], 'profesor': r['profesor']}
    return fa.jsonify(mapa)


@rector_bp.route('/<slug>/rector/profesores')
def rector_profesores(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    page = fa.request.args.get('page', 1, type=int)
    per_page = fa.request.args.get('per_page', 50, type=int)
    per_page = min(max(per_page, 10), 200)
    conn = fa.conectar(slug)
    total = conn.execute('SELECT COUNT(*) as c FROM profesores').fetchone()['c']
    profesores = [dict(r) for r in conn.execute('SELECT id, nombre, email, activo FROM profesores ORDER BY nombre LIMIT ? OFFSET ?',
                                                 (per_page, (page - 1) * per_page)).fetchall()]
    conn.close()
    return fa.render_template('rector_profesores.html',
                           slug=slug, colegio=colegio, rector=rector,
                           profesores=profesores, page=page, per_page=per_page,
                           total=total, total_pages=(total + per_page - 1) // per_page,
                           notif_count=fa.notificaciones_no_leidas(slug, 'rector', rector['id']))


@rector_bp.route('/<slug>/rector/estudiantes')
def rector_estudiantes(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    page = fa.request.args.get('page', 1, type=int)
    per_page = fa.request.args.get('per_page', 50, type=int)
    per_page = min(max(per_page, 10), 200)
    conn = fa.conectar(slug)
    total = conn.execute('SELECT COUNT(*) as c FROM alumnos').fetchone()['c']
    estudiantes = [dict(r) for r in conn.execute('''SELECT id, nombre, curso, jornada, activo FROM alumnos ORDER BY curso, nombre LIMIT ? OFFSET ?''',
                                                  (per_page, (page - 1) * per_page)).fetchall()]
    conn.close()
    return fa.render_template('rector_estudiantes.html',
                           slug=slug, colegio=colegio, rector=rector,
                           estudiantes=estudiantes, page=page, per_page=per_page,
                           total=total, total_pages=(total + per_page - 1) // per_page,
                           notif_count=fa.notificaciones_no_leidas(slug, 'rector', rector['id']))


@rector_bp.route('/<slug>/rector/cursos')
def rector_cursos(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    page = fa.request.args.get('page', 1, type=int)
    per_page = fa.request.args.get('per_page', 12, type=int)
    conn = fa.conectar(slug)
    rows = conn.execute('''SELECT curso, jornada, COUNT(*) as total, SUM(CASE WHEN activo=1 THEN 1 ELSE 0 END) as activos FROM alumnos GROUP BY curso, jornada ORDER BY curso''').fetchall()
    cursos = [dict(r) for r in rows]
    total = len(cursos)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    cursos_page = cursos[start:start + per_page]
    conn.close()
    return fa.render_template('rector_cursos.html',
                           slug=slug, colegio=colegio, rector=rector,
                           cursos=cursos_page, total=total,
                           page=page, per_page=per_page, total_pages=total_pages,
                           notif_count=fa.notificaciones_no_leidas(slug, 'rector', rector['id']))


@rector_bp.route('/<slug>/rector/reportes')
def rector_reportes(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    conn = fa.conectar(slug)
    total_est = conn.execute('SELECT COUNT(*) as c FROM alumnos WHERE activo=1').fetchone()['c']
    total_prof = conn.execute('SELECT COUNT(*) as c FROM profesores WHERE activo=1').fetchone()['c']
    total_cursos = conn.execute('SELECT DISTINCT curso as c FROM alumnos WHERE activo=1').fetchall()
    total_cursos = len(total_cursos)
    total_directoras = conn.execute('SELECT COUNT(*) as c FROM directoras WHERE activo=1').fetchone()['c']
    conn.close()
    return fa.render_template('rector_reportes.html',
                           slug=slug, colegio=colegio, rector=rector,
                           total_est=total_est, total_prof=total_prof,
                           total_cursos=total_cursos,
                           total_directoras=total_directoras,
                           notif_count=fa.notificaciones_no_leidas(slug, 'rector', rector['id']))


@rector_bp.route('/<slug>/rector/asistencia')
def rector_asistencia(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    conn = fa.conectar(slug)
    cursos = [r['curso'] for r in conn.execute('SELECT DISTINCT curso FROM alumnos WHERE activo=1 ORDER BY curso').fetchall()]
    jornadas = [r['jornada'] for r in conn.execute('SELECT DISTINCT jornada FROM alumnos WHERE activo=1 ORDER BY jornada').fetchall()]
    profesores = conn.execute('SELECT id, nombre FROM profesores WHERE activo=1 ORDER BY nombre').fetchall()
    conn.close()
    return fa.render_template('rector_asistencia.html',
                           slug=slug, colegio=colegio, rector=rector,
                           cursos=cursos, jornadas=jornadas,
                           profesores=profesores,
                           estados_asistencia=fa.ESTADOS_ASISTENCIA,
                           hoy_fecha=datetime.today().strftime('%Y-%m-%d'),
                           notif_count=fa.notificaciones_no_leidas(slug, 'rector', rector['id']))


@rector_bp.route('/<slug>/rector/asistencia_data')
def rector_asistencia_data(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.jsonify({'error': 'No autorizado'}), 403
    conn = fa.conectar(slug)
    try:
        curso = fa.request.args.get('curso', '')
        jornada = fa.request.args.get('jornada', '')
        fa.request.args.get('materia', '')
        fa.request.args.get('profesor_id', type=int)
        fecha = fa.request.args.get('fecha', datetime.today().strftime('%Y-%m-%d'))
        try:
            datetime.strptime(fecha, '%Y-%m-%d')
        except ValueError:
            fecha = datetime.today().strftime('%Y-%m-%d')
        where = 'a.activo=1'
        params = []
        if curso:
            where += ' AND a.curso=?'; params.append(curso)
        if jornada:
            where += ' AND a.jornada=?'; params.append(jornada)
        alumnos = conn.execute(f'SELECT a.id, a.nombre, a.num_curso, a.curso, a.jornada FROM alumnos a WHERE {where} ORDER BY a.curso, a.nombre', params).fetchall()
        if not alumnos:
            conn.close()
            return fa.jsonify({'estudiantes': [], 'stats': fa._asistencia_stats(conn, curso, jornada)})
        aids = [a['id'] for a in alumnos]
        placeholders = ','.join('?' * len(aids))
        asis_rows = conn.execute(f'SELECT aid, estado, observacion, hora FROM asistencia WHERE fecha=? AND aid IN ({placeholders})',
                                 (fecha,) + tuple(aids)).fetchall()
        asis_map = {r['aid']: {'estado': r['estado'], 'observacion': r['observacion'] or '', 'hora': r['hora'] or ''} for r in asis_rows}
        estudiantes = []
        for a in alumnos:
            info = asis_map.get(a['id'], {})
            estudiantes.append({
                'id': a['id'], 'nombre': a['nombre'],
                'num_curso': a['num_curso'], 'curso': a['curso'],
                'asistencia': info.get('estado', ''),
                'observacion': info.get('observacion', ''),
                'hora': info.get('hora', ''),
            })
        stats = fa._asistencia_stats(conn, curso, jornada)
        alertas = fa._asistencia_alertas(conn, slug, curso or '', jornada or '') if curso and jornada else []
    finally:
        conn.close()
    return fa.jsonify({'estudiantes': estudiantes, 'stats': stats, 'alertas': alertas,
                    'estados': dict(fa.ESTADOS_ASISTENCIA)})


@rector_bp.route('/<slug>/rector/configuracion', methods=['GET', 'POST'])
def rector_configuracion(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    error = None
    exito = None
    conn = fa.conectar(slug)
    accion = fa.request.form.get('accion', '')
    if fa.request.method == 'POST':
        if not fa.validar_csrf():
            return 'Error de seguridad', 400
        if accion == 'perfil':
            nombre = fa.request.form.get('nombre', '').strip()
            email = fa.request.form.get('email', '').strip()
            password_actual = fa.request.form.get('password_actual', '')
            password_nueva = fa.request.form.get('password_nueva', '')
            if not nombre:
                error = 'El nombre es obligatorio.'
            elif password_nueva and len(password_nueva) < 6:
                error = 'Mínimo 6 caracteres para la nueva contraseña.'
            elif password_nueva and not fa.verificar_pw(password_actual, rector['password']):
                rector2 = conn.execute('SELECT * FROM rectores WHERE id=?', (rector['id'],)).fetchone()
                if rector2 and not fa.verificar_pw(password_actual, rector2['password']):
                    error = 'La contraseña actual no es correcta.'
                else:
                    rector = rector2
            if not error:
                if password_nueva:
                    conn.execute('UPDATE rectores SET nombre=?, email=?, password=? WHERE id=?',
                                 (nombre, email, fa.hash_pw(password_nueva), rector['id']))
                else:
                    conn.execute('UPDATE rectores SET nombre=?, email=? WHERE id=?',
                                 (nombre, email, rector['id']))
                conn.commit()
                exito = 'Perfil actualizado correctamente.'
                rector = conn.execute('SELECT * FROM rectores WHERE id=?', (rector['id'],)).fetchone()

        elif accion == 'institucion':
            tipo_ev = fa.request.form.get('tipo_evaluacion', '').strip()
            esc_min = fa.request.form.get('escala_min', 0, type=float) or 0
            esc_max = fa.request.form.get('escala_max', 5, type=float) or 5
            nota_min = fa.request.form.get('nota_minima_aprobar', 3, type=float) or 3
            decimales = fa.request.form.get('decimales_notas', 0, type=int) or 0
            num_per = fa.request.form.get('num_periodos', 1, type=int) or 1
            acuse = 1 if fa.request.form.get('acuse_recibo') else 0
            roles = fa.request.form.getlist('roles')
            jornadas_lista = fa.request.form.getlist('jornadas')
            roles_json = json.dumps(roles)
            jornadas_json = json.dumps(jornadas_lista)
            conn.execute('''UPDATE config_institucion SET tipo_evaluacion=?, escala_min=?, escala_max=?, nota_minima_aprobar=?,
                            decimales_notas=?, num_periodos=?, acuse_recibo=?,
                            roles_json=?, jornadas_json=?, updated_at=datetime('now','localtime') WHERE slug=?''',
                         (tipo_ev, esc_min, esc_max, nota_min, decimales, num_per, acuse, roles_json, jornadas_json, slug))
            conn.commit()
            fa._cache_invalidate(slug)
            exito = 'Configuración institucional guardada.'

    config = fa.config_get(slug)
    periodos_estado = conn.execute('SELECT * FROM periodos_estado ORDER BY periodo').fetchall()
    conn.close()
    return fa.render_template('rector_configuracion.html',
                           slug=slug, colegio=colegio, rector=rector,
                           config=config, error=error, exito=exito,
                           periodos_estado={r['periodo']: dict(r) for r in periodos_estado},
                           notif_count=fa.notificaciones_no_leidas(slug, 'rector', rector['id']))


@rector_bp.route('/<slug>/rector/periodos/<int:periodo>/<accion>', methods=['POST'])
def rector_periodo_accion(slug, periodo, accion):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return ('No autorizado', 403)
    if not fa.validar_csrf():
        return ('Error CSRF', 403)
    if accion not in ('abrir', 'cerrar'):
        return ('Accion invalida', 400)
    conn = fa.conectar(slug)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if accion == 'cerrar':
        conn.execute('''INSERT INTO periodos_estado (periodo, estado, fecha_cierre, cerrado_por)
                        VALUES (?, 'cerrado', ?, ?)
                        ON CONFLICT(periodo) DO UPDATE SET estado='cerrado', fecha_cierre=?, cerrado_por=?''',
                     (periodo, now, rector['id'], now, rector['id']))
        fa.audit_log(slug, rector['id'], 'periodo_cerrado', 'periodos_estado', registro_id=periodo)
    else:
        conn.execute('''INSERT INTO periodos_estado (periodo, estado, fecha_apertura, abierto_por)
                        VALUES (?, 'abierto', ?, ?)
                        ON CONFLICT(periodo) DO UPDATE SET estado='abierto', fecha_apertura=?, abierto_por=?''',
                     (periodo, now, rector['id'], now, rector['id']))
        fa.audit_log(slug, rector['id'], 'periodo_abierto', 'periodos_estado', registro_id=periodo)
    conn.commit()
    conn.close()
    return fa.redirect(fa.url_for('rector.rector_configuracion', slug=slug, _anchor='periodos'))


@rector_bp.route('/<slug>/rector/solicitudes')
def rector_solicitudes(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    conn = fa.conectar(slug)
    solicitudes = conn.execute('''SELECT s.*, a.nombre as alumno_nombre, p.nombre as profesor_nombre,
                                  COALESCE(ac.nombre, s.tipo) as actividad_nombre
                           FROM solicitudes_modificacion s
                           JOIN alumnos a ON a.id=s.aid
                           LEFT JOIN actividades ac ON ac.id=s.actividad_id
                           JOIN profesores p ON p.id=s.profesor_id
                           WHERE s.slug=?
                           ORDER BY s.fecha_solicitud DESC''', (slug,)).fetchall()
    conn.close()
    return fa.render_template('rector_solicitudes.html',
                           slug=slug, colegio=fa.get_colegio(slug), rector=rector,
                           solicitudes=[dict(s) for s in solicitudes],
                           notif_count=fa.notificaciones_no_leidas(slug, 'rector', rector['id']))


@rector_bp.route('/<slug>/rector/solicitudes/<int:sid>/<accion>', methods=['POST'])
def rector_solicitud_accion(slug, sid, accion):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.jsonify({'status': 'error', 'mensaje': 'No autorizado'}), 403
    if not fa.validar_csrf():
        return fa.jsonify({'status': 'error', 'mensaje': 'Error CSRF'}), 403
    if accion not in ('aprobar', 'rechazar'):
        return fa.jsonify({'status': 'error', 'mensaje': 'Accion invalida'}), 400
    conn = fa.conectar(slug)
    sol = conn.execute('SELECT * FROM solicitudes_modificacion WHERE id=? AND slug=?', (sid, slug)).fetchone()
    if not sol:
        conn.close()
        return fa.jsonify({'status': 'error', 'mensaje': 'Solicitud no encontrada'}), 404
    if sol['estado'] != 'pendiente':
        conn.close()
        return fa.jsonify({'status': 'error', 'mensaje': 'La solicitud ya fue ' + sol['estado']}), 400
    if sol['profesor_id'] == rector['id']:
        conn.close()
        return fa.jsonify({'status': 'error', 'mensaje': 'No puedes aprobar tu propia solicitud'}), 403
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if accion == 'aprobar':
        valor_sol = float(sol['valor_solicitado']) if sol['valor_solicitado'] else None
        curso_ctx = sol['curso']
        materia_ctx = sol['materia']
        if sol['tipo'] == 'actividad' and sol['actividad_id'] is not None:
            conn.execute('''INSERT INTO notas (aid,actividad_id,val) VALUES (?,?,?)
                            ON CONFLICT(aid,actividad_id) DO UPDATE SET val=excluded.val''',
                         (sol['aid'], sol['actividad_id'], valor_sol))
            conn.commit()
            fa.auditar_nota(slug, rector['id'], 'rector', 'modificacion', 'notas', sol['aid'],
                          curso_ctx, materia_ctx, sol['periodo'],
                          campo='nota', actividad_id=sol['actividad_id'],
                          valor_anterior=sol['valor_actual'], valor_nuevo=valor_sol,
                          motivo='Aprobado por rector (solicitud #%d)' % sid)
        elif sol['tipo'] in ('evaluacion', 'autoevaluacion'):
            jornada_eval = sol['jornada']
            if sol['tipo'] == 'evaluacion':
                conn.execute('''INSERT INTO evaluaciones (aid,profesor_id,materia,jornada,evaluacion,periodo)
                                VALUES (?,?,?,?,?,?)
                                ON CONFLICT(aid,profesor_id,materia,jornada,periodo)
                                DO UPDATE SET evaluacion=excluded.evaluacion''',
                             (sol['aid'], sol['profesor_id'], materia_ctx, jornada_eval, valor_sol, sol['periodo']))
            else:
                conn.execute('''INSERT INTO evaluaciones (aid,profesor_id,materia,jornada,autoevaluacion,periodo)
                                VALUES (?,?,?,?,?,?)
                                ON CONFLICT(aid,profesor_id,materia,jornada,periodo)
                                DO UPDATE SET autoevaluacion=excluded.autoevaluacion''',
                             (sol['aid'], sol['profesor_id'], materia_ctx, jornada_eval, valor_sol, sol['periodo']))
            conn.commit()
            fa.auditar_nota(slug, rector['id'], 'rector', 'modificacion', 'evaluaciones', sol['aid'],
                          curso_ctx, materia_ctx, sol['periodo'],
                          campo=sol['tipo'],
                          valor_anterior=sol['valor_actual'], valor_nuevo=valor_sol,
                          motivo='Aprobado por rector (solicitud #%d)' % sid)
        conn.execute('''UPDATE solicitudes_modificacion SET estado='aprobada', aprobado_por=?, fecha_respuesta=? WHERE id=?''',
                     (rector['id'], now, sid))
        conn.commit()
        fa.crear_notificacion(slug, 'profesor', sol['profesor_id'],
                            'Solicitud aprobada', 'Tu solicitud #%d fue aprobada por el rector.' % sid)
    else:
        conn.execute('''UPDATE solicitudes_modificacion SET estado='rechazada', aprobado_por=?, fecha_respuesta=? WHERE id=?''',
                     (rector['id'], now, sid))
        conn.commit()
        fa.auditar_nota(slug, rector['id'], 'rector', 'solicitud_rechazada', 'solicitudes_modificacion', sol['aid'],
                      sol['curso'], sol['materia'], sol['periodo'],
                      campo=sol['tipo'], actividad_id=sol['actividad_id'],
                      valor_anterior=sol['valor_actual'], valor_nuevo=sol['valor_solicitado'],
                      motivo='Rechazado por rector (solicitud #%d)' % sid)
        fa.crear_notificacion(slug, 'profesor', sol['profesor_id'],
                            'Solicitud rechazada', 'Tu solicitud #%d fue rechazada por el rector.' % sid)
    conn.close()
    return fa.jsonify({'status': 'ok', 'mensaje': 'Solicitud ' + ('aprobada' if accion == 'aprobar' else 'rechazada')})


@rector_bp.route('/<slug>/rector/auditoria')
def rector_auditoria(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    conn = fa.conectar(slug)
    tabla = fa.request.args.get('tabla', '')
    page = max(1, int(fa.request.args.get('page', 1)))
    limit = 50
    offset = (page - 1) * limit
    where = []
    params = []
    if tabla:
        where.append('a.tabla = ?')
        params.append(tabla)
    where_clause = ('WHERE ' + ' AND '.join(where)) if where else ''
    total = conn.execute(f'SELECT COUNT(*) as c FROM audit_log a {where_clause}', params).fetchone()['c']
    registros = conn.execute(f'''SELECT a.*, u.nombre as usuario_nombre
                                 FROM audit_log a
                                 LEFT JOIN usuarios u ON a.usuario_id = u.id
                                 {where_clause}
                                 ORDER BY a.creado DESC LIMIT ? OFFSET ?''', params + [limit, offset]).fetchall()
    tablas = [r['tabla'] for r in conn.execute("SELECT DISTINCT tabla FROM audit_log ORDER BY tabla").fetchall()]
    conn.close()
    total_pages = max(1, (total + limit - 1) // limit)
    return fa.render_template('rector_auditoria.html',
                           slug=slug, colegio=colegio, rector=rector,
                           registros=[dict(r) for r in registros],
                           tabla=tabla, tablas=tablas,
                           page=page, total_pages=total_pages, total=total,
                           notif_count=fa.notificaciones_no_leidas(slug, 'rector', rector['id']))


@rector_bp.route('/<slug>/rector/comunicaciones')
def rector_comunicaciones(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    estado_filtro = fa.request.args.get('estado', '')
    conn = fa.conectar(slug)
    if estado_filtro:
        comunicaciones = conn.execute('''SELECT * FROM comunicaciones WHERE rector_id=? AND activo=1 AND estado=?
                                         ORDER BY fecha_creacion DESC''',
                                      (rector['id'], estado_filtro)).fetchall()
    else:
        comunicaciones = conn.execute('''SELECT * FROM comunicaciones WHERE rector_id=? AND activo=1
                                         ORDER BY fecha_creacion DESC''',
                                      (rector['id'],)).fetchall()
    notif_count = fa.notificaciones_no_leidas(slug, 'rector', rector['id'])
    conn.close()
    return fa.render_template('rector_comunicaciones.html',
                           slug=slug, colegio=colegio, rector=rector,
                           comunicaciones=comunicaciones,
                           estado_filtro=estado_filtro,
                           notif_count=notif_count)


@rector_bp.route('/<slug>/rector/comunicaciones/nueva', methods=['GET', 'POST'])
def rector_comunicacion_nueva(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    error = None
    exito = None
    conn = fa.conectar(slug)
    cursos = [r['curso'] for r in conn.execute('SELECT DISTINCT curso FROM alumnos WHERE activo=1 ORDER BY curso').fetchall()]
    profesores = [dict(r) for r in conn.execute('SELECT id, nombre FROM profesores WHERE activo=1 ORDER BY nombre').fetchall()]
    directoras = [dict(r) for r in conn.execute('SELECT id, nombre, curso FROM directoras WHERE activo=1 ORDER BY nombre').fetchall()]
    conn.close()
    if fa.request.method == 'POST':
        if not fa.validar_csrf():
            return 'Error de seguridad', 400
        titulo = fa.request.form.get('titulo', '').strip()
        contenido = fa.request.form.get('contenido', '').strip()
        dest_tipo = fa.request.form.get('destinatario_tipo', '').strip()
        dest_valor = fa.request.form.get('destinatario_valor', '').strip()
        prioridad = fa.request.form.get('prioridad', 'normal').strip()
        programar = fa.request.form.get('fecha_programada', '').strip()
        publicar_ahora = fa.request.form.get('publicar_ahora', '0').strip()
        if not titulo or not contenido or not dest_tipo:
            error = 'Completa todos los campos.'
        else:
            conn = fa.conectar(slug)
            cursor = conn.execute(
                '''INSERT INTO comunicaciones (rector_id,titulo,contenido,destinatario_tipo,destinatario_valor,prioridad,estado,fecha_programada,fecha_publicacion)
                   VALUES (?,?,?,?,?,?,?,?,?)''',
                (rector['id'], titulo, contenido, dest_tipo, dest_valor, prioridad,
                 'publicado' if publicar_ahora == '1' else ('programado' if programar else 'borrador'),
                 programar if programar else None,
                 datetime.today().strftime('%Y-%m-%d %H:%M:%S') if publicar_ahora == '1' else None))
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()
            if publicar_ahora == '1':
                try:
                    fa.generar_destinatarios(slug, new_id)
                except Exception as e:
                    fa.app.logger.error(f'Error en generar_destinatarios (nueva): {e}')
            exito = 'Comunicación creada correctamente.'
    return fa.render_template('rector_comunicacion_form.html',
                           slug=slug, colegio=colegio, rector=rector,
                           error=error, exito=exito, comunicacion=None,
                           cursos=cursos, profesores=profesores,
                           directoras=directoras,
                           notif_count=fa.notificaciones_no_leidas(slug, 'rector', rector['id']))


@rector_bp.route('/<slug>/rector/comunicaciones/<int:cid>/editar', methods=['GET', 'POST'])
def rector_comunicacion_editar(slug, cid):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    conn = fa.conectar(slug)
    com = conn.execute('SELECT * FROM comunicaciones WHERE id=? AND rector_id=? AND activo=1',
                       (cid, rector['id'])).fetchone()
    if not com:
        conn.close()
        return 'Comunicación no encontrada', 404
    cursos = [r['curso'] for r in conn.execute('SELECT DISTINCT curso FROM alumnos WHERE activo=1 ORDER BY curso').fetchall()]
    profesores = [dict(r) for r in conn.execute('SELECT id, nombre FROM profesores WHERE activo=1 ORDER BY nombre').fetchall()]
    directoras = [dict(r) for r in conn.execute('SELECT id, nombre, curso FROM directoras WHERE activo=1 ORDER BY nombre').fetchall()]
    error = None
    exito = None
    if fa.request.method == 'POST':
        if not fa.validar_csrf():
            return 'Error de seguridad', 400
        titulo = fa.request.form.get('titulo', '').strip()
        contenido = fa.request.form.get('contenido', '').strip()
        dest_tipo = fa.request.form.get('destinatario_tipo', '').strip()
        dest_valor = fa.request.form.get('destinatario_valor', '').strip()
        prioridad = fa.request.form.get('prioridad', 'normal').strip()
        programar = fa.request.form.get('fecha_programada', '').strip()
        publicar_ahora = fa.request.form.get('publicar_ahora', '0').strip()
        if not titulo or not contenido or not dest_tipo:
            error = 'Completa todos los campos.'
        else:
            conn.execute(
                '''UPDATE comunicaciones SET titulo=?,contenido=?,destinatario_tipo=?,destinatario_valor=?,
                   prioridad=?,estado=?,fecha_programada=?,fecha_publicacion=?
                   WHERE id=? AND rector_id=?''',
                (titulo, contenido, dest_tipo, dest_valor, prioridad,
                 'publicado' if publicar_ahora == '1' else ('programado' if programar else com['estado']),
                 programar if programar else None,
                 datetime.today().strftime('%Y-%m-%d %H:%M:%S') if publicar_ahora == '1' else (com['fecha_publicacion'] if com['fecha_publicacion'] else None),
                 cid, rector['id']))
            conn.commit()
            if publicar_ahora == '1':
                conn.close()
                try:
                    fa.generar_destinatarios(slug, cid)
                except Exception as e:
                    fa.app.logger.error(f'Error en generar_destinatarios: {e}')
                conn = fa.conectar(slug)
            exito = 'Comunicación actualizada correctamente.'
            com = conn.execute('SELECT * FROM comunicaciones WHERE id=? AND activo=1', (cid,)).fetchone()
    conn.close()
    return fa.render_template('rector_comunicacion_form.html',
                           slug=slug, colegio=colegio, rector=rector,
                           error=error, exito=exito, comunicacion=com,
                           cursos=cursos, profesores=profesores,
                           directoras=directoras,
                           notif_count=fa.notificaciones_no_leidas(slug, 'rector', rector['id']))


@rector_bp.route('/<slug>/rector/comunicaciones/<int:cid>')
def rector_comunicacion_detalle(slug, cid):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    conn = fa.conectar(slug)
    com = conn.execute('SELECT * FROM comunicaciones WHERE id=? AND rector_id=? AND activo=1',
                       (cid, rector['id'])).fetchone()
    if not com:
        conn.close()
        return 'Comunicación no encontrada', 404
    total_dest = conn.execute('SELECT COUNT(*) as c FROM comunicaciones_leidas WHERE comunicacion_id=?', (cid,)).fetchone()['c']
    leidas_count = conn.execute('SELECT COUNT(*) as c FROM comunicaciones_leidas WHERE comunicacion_id=? AND leido=1', (cid,)).fetchone()['c']
    no_leidas = total_dest - leidas_count
    conn.close()
    return fa.render_template('rector_comunicacion_detail.html',
                           slug=slug, colegio=colegio, rector=rector,
                           com=com, total_dest=total_dest, leidas=leidas_count, no_leidas=no_leidas,
                           notif_count=fa.notificaciones_no_leidas(slug, 'rector', rector['id']))


@rector_bp.route('/<slug>/rector/comunicaciones/<int:cid>/publicar', methods=['POST'])
def rector_comunicacion_publicar(slug, cid):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    if not fa.validar_csrf():
        return 'Error de seguridad', 400
    conn = fa.conectar(slug)
    conn.execute('''UPDATE comunicaciones SET estado='publicado',fecha_publicacion=datetime('now','localtime')
                    WHERE id=? AND rector_id=? AND activo=1''', (cid, rector['id']))
    conn.commit()
    conn.close()
    try:
        fa.generar_destinatarios(slug, cid)
    except Exception as e:
        fa.app.logger.error(f'Error en generar_destinatarios (publicar): {e}')
    return fa.redirect(fa.url_for('rector.rector_comunicaciones', slug=slug))


@rector_bp.route('/<slug>/rector/comunicaciones/<int:cid>/archivar', methods=['POST'])
def rector_comunicacion_archivar(slug, cid):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    if not fa.validar_csrf():
        return 'Error de seguridad', 400
    conn = fa.conectar(slug)
    conn.execute("UPDATE comunicaciones SET estado='archivado' WHERE id=? AND rector_id=? AND activo=1",
                 (cid, rector['id']))
    conn.commit()
    conn.close()
    return fa.redirect(fa.url_for('rector.rector_comunicaciones', slug=slug))


@rector_bp.route('/<slug>/rector/comunicaciones/<int:cid>/eliminar', methods=['POST'])
def rector_comunicacion_eliminar(slug, cid):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    if not fa.validar_csrf():
        return 'Error de seguridad', 400
    conn = fa.conectar(slug)
    conn.execute('DELETE FROM comunicaciones WHERE id=? AND rector_id=?', (cid, rector['id']))
    conn.execute('DELETE FROM comunicaciones_leidas WHERE comunicacion_id=?', (cid,))
    conn.commit()
    conn.close()
    return fa.redirect(fa.url_for('rector.rector_comunicaciones', slug=slug))


@rector_bp.route('/<slug>/rector/comunicaciones/<int:cid>/evento')
def rector_comunicacion_evento(slug, cid):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.jsonify({'error': 'No autorizado'}), 403
    conn = fa.conectar(slug)
    com = conn.execute('SELECT id, titulo, fecha_programada, prioridad FROM comunicaciones WHERE id=? AND rector_id=? AND activo=1',
                       (cid, rector['id'])).fetchone()
    conn.close()
    if not com:
        return fa.jsonify({'error': 'No encontrada'}), 404
    return fa.jsonify({
        'id': com['id'],
        'title': com['titulo'],
        'start': com['fecha_programada'] or datetime.today().strftime('%Y-%m-%d'),
        'className': 'event-' + com['prioridad']
    })


@rector_bp.route('/<slug>/rector/canales')
def rector_canales(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.rector_login', slug=slug))
    conn = fa.conectar(slug)
    canales = conn.execute('SELECT * FROM canales WHERE slug=? ORDER BY fecha_creacion DESC', (slug,)).fetchall()
    cursos = conn.execute('SELECT DISTINCT curso FROM alumnos WHERE activo=1 ORDER BY curso').fetchall()
    materias_rows = conn.execute('SELECT DISTINCT materia FROM actividades').fetchall()
    if not materias_rows:
        materias_rows = conn.execute('SELECT DISTINCT materia FROM asignaciones_materia').fetchall()
    materias = list(set(r['materia'] for r in materias_rows))
    conn.close()
    colegio = fa.get_colegio(slug)
    return fa.render_template('rector_canales.html', slug=slug, rector=rector, canales=canales, colegio=colegio,
                           cursos=[r['curso'] for r in cursos], materias=materias)


@rector_bp.route('/<slug>/rector/canales/crear', methods=['POST'])
def rector_canales_crear(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.jsonify({'ok': False, 'error': 'No autorizado'})
    if not fa.validar_csrf():
        return fa.jsonify({'ok': False, 'error': 'Error CSRF'}), 403
    tipo = fa.request.form.get('tipo')
    nombre = fa.request.form.get('nombre', '').strip()
    curso = fa.request.form.get('curso', '')
    materia = fa.request.form.get('materia', '')
    descripcion = fa.request.form.get('descripcion', '')
    if not nombre:
        nombres = {'institucional': 'Institucional', 'rectoria': 'Rectoría', 'profesores': 'Profesores',
                   'director_curso': f'Directores {curso}', 'curso': f'Curso {curso}', 'materia': f'Materia {materia}'}
        nombre = nombres.get(tipo, tipo)
    conn = fa.conectar(slug)
    cid = conn.execute('INSERT INTO canales (slug,rector_id,tipo,nombre,descripcion,curso,materia) VALUES (?,?,?,?,?,?,?)',
                       (slug, rector['id'], tipo, nombre, descripcion, curso, materia)).lastrowid
    fa.asignar_miembros_auto(conn, slug, cid, tipo, curso, materia)
    conn.commit()
    conn.close()
    return fa.jsonify({'ok': True, 'canal_id': cid})


@rector_bp.route('/<slug>/rector/canales/<int:cid>/eliminar', methods=['POST'])
def rector_canales_eliminar(slug, cid):
    fa = _fa()
    if not fa.validar_csrf():
        return fa.jsonify({'ok': False, 'error': 'Error CSRF'}), 403
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.jsonify({'ok': False, 'error': 'No autorizado'})
    conn = fa.conectar(slug)
    conn.execute('UPDATE canales SET activo=0 WHERE id=? AND slug=?', (cid, slug))
    conn.commit()
    conn.close()
    return fa.jsonify({'ok': True})


@rector_bp.route('/<slug>/rector/canales/<int:cid>/miembros')
def rector_canales_miembros(slug, cid):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.jsonify({'ok': False, 'error': 'No autorizado'})
    conn = fa.conectar(slug)
    miembros = conn.execute('SELECT * FROM canal_miembros WHERE canal_id=?', (cid,)).fetchall()
    canal = conn.execute('SELECT * FROM canales WHERE id=?', (cid,)).fetchone()
    conn.close()
    data = [dict(m) for m in miembros]
    conn2 = fa.conectar(slug)
    for m in data:
        m['nombre_usuario'] = _nombre_usuario_canal(conn2, m['usuario_tipo'], m['usuario_id'])
    conn2.close()
    return fa.jsonify({'ok': True, 'miembros': data, 'canal': dict(canal) if canal else None})


@rector_bp.route('/<slug>/rector/gestion-rectores')
def rector_gestion(slug):
    fa = _fa()
    r = fa.require_rector_principal(slug)
    colegio = fa.get_colegio(slug)
    conn = fa.conectar(slug)
    rectores = conn.execute('SELECT id, nombre, usuario, email, activo, es_principal FROM rectores ORDER BY es_principal DESC, id').fetchall()
    notif_count = fa.notificaciones_no_leidas(slug, 'rector', r['id'])
    conn.close()
    return fa.render_template('rector_gestion.html',
                           slug=slug, colegio=colegio, rector=r,
                           rectores=rectores, notif_count=notif_count)


@rector_bp.route('/<slug>/rector/gestion-rectores/crear', methods=['GET', 'POST'])
def rector_gestion_crear(slug):
    fa = _fa()
    r = fa.require_rector_principal(slug)
    colegio = fa.get_colegio(slug)
    error = None
    exito = None
    if fa.request.method == 'POST':
        if not fa.validar_csrf():
            return 'Error de seguridad', 400
        nombre = fa.request.form.get('nombre', '').strip()
        usuario = fa.request.form.get('usuario', '').strip()
        password = fa.request.form.get('password', '').strip()
        confirmar = fa.request.form.get('confirmar_password', '').strip()
        email = fa.request.form.get('email', '').strip()
        if not nombre or not usuario or not password:
            error = 'Completa todos los campos obligatorios.'
        elif len(password) < 6:
            error = 'Mínimo 6 caracteres para la contraseña.'
        elif password != confirmar:
            error = 'Las contraseñas no coinciden.'
        else:
            conn = fa.conectar(slug)
            if conn.execute('SELECT 1 FROM rectores WHERE usuario=?', (usuario,)).fetchone():
                error = 'Ese usuario ya existe.'
            else:
                conn.execute('INSERT INTO rectores (nombre, usuario, password, email) VALUES (?, ?, ?, ?)',
                             (nombre, usuario, fa.hash_pw(password), email))
                conn.commit()
                exito = f'Rector "{nombre}" creado correctamente.'
                fa.crear_notificacion(slug, 'rector', r['id'],
                                    'Nuevo rector creado', f'Se creó el rector {nombre} ({usuario}).', 'success')
            conn.close()
    return fa.render_template('rector_gestion.html',
                           slug=slug, colegio=colegio, rector=r,
                           error=error, exito=exito, crear=True,
                           notif_count=fa.notificaciones_no_leidas(slug, 'rector', r['id']))


@rector_bp.route('/<slug>/rector/gestion-rectores/<int:rid>/editar', methods=['GET', 'POST'])
def rector_gestion_editar(slug, rid):
    fa = _fa()
    r = fa.require_rector_principal(slug)
    colegio = fa.get_colegio(slug)
    conn = fa.conectar(slug)
    target = conn.execute('SELECT * FROM rectores WHERE id=?', (rid,)).fetchone()
    if not target:
        conn.close()
        return 'Rector no encontrado', 404
    error = None
    exito = None
    if fa.request.method == 'POST':
        if not fa.validar_csrf():
            return 'Error de seguridad', 400
        nombre = fa.request.form.get('nombre', '').strip()
        usuario = fa.request.form.get('usuario', '').strip()
        password = fa.request.form.get('password', '').strip()
        confirmar = fa.request.form.get('confirmar_password', '').strip()
        email = fa.request.form.get('email', '').strip()
        if not nombre or not usuario:
            error = 'Nombre y usuario son obligatorios.'
        elif password and len(password) < 6:
            error = 'Mínimo 6 caracteres.'
        elif password and password != confirmar:
            error = 'Las contraseñas no coinciden.'
        else:
            existing = conn.execute('SELECT 1 FROM rectores WHERE usuario=? AND id!=?', (usuario, rid)).fetchone()
            if existing:
                error = 'Ese nombre de usuario ya está en uso.'
            else:
                if password:
                    conn.execute('UPDATE rectores SET nombre=?, usuario=?, password=?, email=? WHERE id=?',
                                 (nombre, usuario, fa.hash_pw(password), email, rid))
                else:
                    conn.execute('UPDATE rectores SET nombre=?, usuario=?, email=? WHERE id=?',
                                 (nombre, usuario, email, rid))
                conn.commit()
                exito = 'Rector actualizado correctamente.'
                target = conn.execute('SELECT * FROM rectores WHERE id=?', (rid,)).fetchone()
    conn.close()
    return fa.render_template('rector_gestion.html',
                           slug=slug, colegio=colegio, rector=r,
                           error=error, exito=exito, editar=target,
                           notif_count=fa.notificaciones_no_leidas(slug, 'rector', r['id']))


@rector_bp.route('/<slug>/rector/gestion-rectores/<int:rid>/toggle', methods=['POST'])
def rector_gestion_toggle(slug, rid):
    fa = _fa()
    r = fa.require_rector_principal(slug)
    if not fa.validar_csrf():
        return 'Error de seguridad', 400
    if rid == r['id']:
        return 'No puedes desactivarte a ti mismo.', 400
    conn = fa.conectar(slug)
    conn.execute('UPDATE rectores SET activo = CASE WHEN activo=1 THEN 0 ELSE 1 END WHERE id=?', (rid,))
    conn.commit()
    conn.close()
    return fa.redirect(fa.url_for('rector.rector_gestion', slug=slug))


@rector_bp.route('/<slug>/rector/gestion-rectores/<int:rid>/eliminar', methods=['POST'])
def rector_gestion_eliminar(slug, rid):
    fa = _fa()
    r = fa.require_rector_principal(slug)
    if not fa.validar_csrf():
        return 'Error de seguridad', 400
    if rid == r['id']:
        return 'No puedes eliminar tu propia cuenta.', 400
    conn = fa.conectar(slug)
    target = conn.execute('SELECT es_principal FROM rectores WHERE id=?', (rid,)).fetchone()
    if not target:
        conn.close()
        return 'Rector no encontrado', 404
    if target['es_principal']:
        conn.close()
        return 'No puedes eliminar al Rector Principal. Transfiere el rol primero.', 400
    conn.execute('DELETE FROM rectores WHERE id=?', (rid,))
    conn.commit()
    conn.close()
    return fa.redirect(fa.url_for('rector.rector_gestion', slug=slug))


@rector_bp.route('/<slug>/rector/gestion-rectores/<int:rid>/hacer-principal', methods=['POST'])
def rector_gestion_hacer_principal(slug, rid):
    fa = _fa()
    r = fa.require_rector_principal(slug)
    if not fa.validar_csrf():
        return 'Error de seguridad', 400
    if rid == r['id']:
        return 'Ya eres el Rector Principal.', 400
    conn = fa.conectar(slug)
    target = conn.execute('SELECT id, activo FROM rectores WHERE id=?', (rid,)).fetchone()
    if not target:
        conn.close()
        return 'Rector no encontrado', 404
    if not target['activo']:
        conn.close()
        return 'No puedes transferir el rol a un rector inactivo.', 400
    conn.execute('UPDATE rectores SET es_principal=0 WHERE id=?', (r['id'],))
    conn.execute('UPDATE rectores SET es_principal=1 WHERE id=?', (rid,))
    conn.commit()
    conn.close()
    fa.session[f'rector_id_{slug}'] = rid
    fa.crear_notificacion(slug, 'rector', rid,
                         'Rector Principal transferido', f'{r["nombre"]} te ha transferido el rol de Rector Principal.', 'warning')
    return fa.redirect(fa.url_for('rector.rector_panel', slug=slug))


@rector_bp.route('/<slug>/rector/expediente')
def rector_expediente(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    conn = fa.conectar(slug)
    try:
        colegio = fa.get_colegio(slug)
        aid = fa.request.args.get('aid', type=int) or fa.request.args.get('alumno_id', type=int)
        alumno = None
        notas_por_materia = {}
        asistencia = []
        observaciones = []
        cursos_raw = conn.execute('SELECT DISTINCT curso FROM alumnos WHERE activo=1 ORDER BY curso').fetchall()
        cursos = [r['curso'] for r in cursos_raw]
        notif_count = fa.notificaciones_no_leidas(slug, 'rector', rector['id'])
        if aid:
            alumno = conn.execute('SELECT * FROM alumnos WHERE id=?', (aid,)).fetchone()
            if alumno:
                notas_raw = conn.execute('''SELECT a.materia, ROUND(AVG(n.val), 1) AS promedio, COUNT(n.id) AS evaluaciones
                                            FROM notas n JOIN actividades a ON a.id = n.actividad_id
                                            WHERE n.aid=? GROUP BY a.materia ORDER BY promedio DESC''', (aid,)).fetchall()
                notas_por_materia = {r['materia']: {'promedio': r['promedio'], 'evaluaciones': r['evaluaciones']} for r in notas_raw}
                asistencia = conn.execute('SELECT fecha, estado, observacion FROM asistencia WHERE aid=? ORDER BY fecha DESC LIMIT 20', (aid,)).fetchall()
                observaciones = conn.execute('SELECT o.* FROM observador_registros o WHERE o.aid=? ORDER BY o.fecha DESC LIMIT 50', (aid,)).fetchall()
        return fa.render_template('rector/expediente.html', slug=slug, colegio=colegio, rector=rector,
                               alumno=alumno, notas_por_materia=notas_por_materia, asistencia=asistencia,
                               observaciones=observaciones, cursos=cursos, notif_count=notif_count)
    finally:
        conn.close()


@rector_bp.route('/<slug>/rector/observador')
def rector_observador(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    notif_count = fa.notificaciones_no_leidas(slug, 'rector', rector['id'])
    return fa.render_template('rector/observador.html', slug=slug, colegio=colegio, rector=rector, notif_count=notif_count)


@rector_bp.route('/<slug>/rector/certificados')
def rector_certificados(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    notif_count = fa.notificaciones_no_leidas(slug, 'rector', rector['id'])
    conn = fa.conectar(slug)
    try:
        cursos_raw = conn.execute('SELECT DISTINCT curso FROM alumnos WHERE activo=1 ORDER BY curso').fetchall()
    finally:
        conn.close()
    cursos = [r['curso'] for r in cursos_raw]
    return fa.render_template('rector/certificados.html', slug=slug, colegio=colegio, rector=rector, cursos=cursos, notif_count=notif_count)


@rector_bp.route('/<slug>/api/rector/certificados/<tipo>')
def api_rector_certificados(slug, tipo):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.jsonify({'ok': False, 'error': 'No autorizado'}), 401
    aid = fa.request.args.get('estudiante_id', type=int)
    if not aid:
        return fa.jsonify({'ok': False, 'error': 'estudiante_id requerido'}), 400
    conn = fa.conectar(slug)
    try:
        alumno = conn.execute('SELECT * FROM alumnos WHERE id=?', (aid,)).fetchone()
        if not alumno:
            return fa.jsonify({'ok': False, 'error': 'Estudiante no encontrado'}), 404
        colegio = fa.get_colegio(slug) or {}
        firma = rector['nombre']
        from app.services.certificates import (
            generar_certificado_conducta,
            generar_certificado_estudio,
            generar_constancia_estudio,
            generar_paz_y_salvo,
        )
        if tipo == 'constancia':
            buf = generar_constancia_estudio(dict(alumno), colegio, firma)
        elif tipo == 'paz-y-salvo':
            buf = generar_paz_y_salvo(dict(alumno), colegio, firma)
        elif tipo == 'conducta':
            obs_rows = conn.execute(
                'SELECT texto FROM observaciones WHERE aid=? ORDER BY fecha DESC LIMIT 20',
                (aid,)).fetchall()
            observaciones = [{'texto': r['texto'] or ''} for r in obs_rows]
            buf = generar_certificado_conducta(dict(alumno), colegio, observaciones, firma)
        elif tipo == 'estudio':
            curso = alumno['curso']
            jornada = alumno['jornada']
            maxp = conn.execute(
                'SELECT MAX(COALESCE(periodo,1)) as m FROM actividades WHERE curso=? AND jornada=?',
                (curso, jornada)).fetchone()['m']
            periodo = maxp or 1
            lista_materias = [r['materia'] for r in conn.execute(
                'SELECT DISTINCT materia FROM actividades WHERE curso=? AND jornada=? '
                'AND COALESCE(periodo,1)=? ORDER BY materia',
                (curso, jornada, periodo)).fetchall()]
            materias_set = set(lista_materias)
            notas_all = conn.execute(
                '''SELECT ac.materia, n.val FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
                   WHERE n.aid=? AND ac.curso=? AND ac.jornada=? AND COALESCE(ac.periodo,1)=?''',
                (aid, curso, jornada, periodo)).fetchall()
            ev_all = conn.execute(
                '''SELECT materia, evaluacion, autoevaluacion FROM evaluaciones
                   WHERE aid=? AND jornada=? AND COALESCE(periodo,1)=?''',
                (aid, jornada, periodo)).fetchall()
            notas_por_mat = {}
            for r in notas_all:
                if r['materia'] in materias_set:
                    notas_por_mat.setdefault(r['materia'], []).append(r['val'])
            ev_por_mat = {}
            for r in ev_all:
                if r['materia'] in materias_set:
                    ev_por_mat[r['materia']] = r
            materias = []
            todos_finales = []
            for mat in lista_materias:
                ev = ev_por_mat.get(mat)
                eval_v = ev['evaluacion'] if ev and ev['evaluacion'] is not None else None
                auto_v = ev['autoevaluacion'] if ev and ev['autoevaluacion'] is not None else None
                final = fa._promedio_ponderado(notas_por_mat.get(mat, []), eval_v, auto_v)
                if final is not None:
                    materias.append({'nombre': mat, 'nota': round(final, 1)})
                    todos_finales.append(final)
            promedio = round(sum(todos_finales) / len(todos_finales), 1) if todos_finales else 0
            buf = generar_certificado_estudio(dict(alumno), colegio, materias, promedio, firma)
        else:
            return fa.jsonify({'ok': False, 'error': 'Tipo de certificado inválido'}), 400
        resp = Response(buf.getvalue(), mimetype='application/pdf')
        resp.headers['Content-Disposition'] = f"inline; filename=certificado_{tipo}.pdf"
        return resp
    finally:
        conn.close()


@rector_bp.route('/<slug>/rector/calendario')
def rector_calendario(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    notif_count = fa.notificaciones_no_leidas(slug, 'rector', rector['id'])
    return fa.render_template('rector/calendario.html', slug=slug, colegio=colegio, rector=rector, notif_count=notif_count)


@rector_bp.route('/<slug>/rector/mensajes')
def rector_mensajes(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    notif_count = fa.notificaciones_no_leidas(slug, 'rector', rector['id'])
    return fa.render_template('rector/mensajes.html', slug=slug, colegio=colegio, rector=rector, notif_count=notif_count)


@rector_bp.route('/<slug>/api/rector/estudiantes')
def api_rector_estudiantes(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.jsonify({'ok': False, 'error': 'No autorizado'}), 401
    conn = fa.conectar(slug)
    try:
        q = fa.request.args.get('q', '').strip()
        curso = fa.request.args.get('curso', '').strip()
        if curso:
            rows = conn.execute('SELECT a.id, a.nombre, a.curso FROM alumnos a WHERE a.curso=? AND a.activo=1 ORDER BY a.nombre', (curso,)).fetchall()
            return fa.jsonify({'estudiantes': [dict(r) for r in rows]})
        if len(q) < 2:
            return fa.jsonify({'ok': False, 'data': []})
        rows = conn.execute('''SELECT a.id, a.nombre, a.curso FROM alumnos a WHERE a.nombre LIKE ? ORDER BY a.nombre LIMIT 15''', (f'%{q}%',)).fetchall()
        return fa.jsonify({'ok': True, 'data': [dict(r) for r in rows]})
    finally:
        conn.close()


@rector_bp.route('/<slug>/api/rector/observador/<int:aid>', methods=['GET', 'POST'])
def api_rector_observador(slug, aid):
    fa = _fa()
    fa.require_colegio(slug)
    rector = fa.get_rector(slug)
    if not rector:
        return fa.jsonify({'ok': False, 'error': 'No autorizado'}), 401
    conn = fa.conectar(slug)
    try:
        if fa.request.method == 'POST':
            if not fa.validar_csrf():
                return fa.jsonify({'ok': False, 'error': 'CSRF inválido'}), 400
            data = fa.request.get_json(silent=True) or {}
            tipo = data.get('tipo', 'llamado')
            texto = data.get('texto', '').strip()
            if not texto:
                return fa.jsonify({'ok': False, 'error': 'Texto requerido'}), 400
            conn.execute('''INSERT INTO observador_registros (slug, aid, tipo, texto, docente, estado)
                            VALUES (?,?,?,?,?,?)''',
                         (slug, aid, tipo, texto, fa.session.get('nombre', ''), 'pendiente'))
            conn.commit()
            return fa.jsonify({'ok': True})
        rows = conn.execute('''SELECT o.*, CASE o.tipo
                                WHEN 'positivo' THEN 'Positivo'
                                WHEN 'llamado' THEN 'Llamado de atención'
                                WHEN 'compromiso' THEN 'Compromiso'
                                WHEN 'seguimiento' THEN 'Seguimiento'
                            END AS tipo_label
                            FROM observador_registros o
                            WHERE o.aid=? AND o.slug=?
                            ORDER BY o.fecha DESC LIMIT 50''', (aid, slug)).fetchall()
        return fa.jsonify({'ok': True, 'data': [dict(r) for r in rows]})
    finally:
        conn.close()


@rector_bp.route('/<slug>/gestion-academica/alumnos')
def rector_gestion_alumnos(slug):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify([]), 403
    conn = fa.conectar(slug)
    try:
        q = fa.request.args.get('q', '').strip()
        if q:
            alumnos = conn.execute(
                "SELECT id, nombre, curso, jornada FROM alumnos WHERE activo=1 AND nombre LIKE ? ORDER BY nombre",
                (f'%{q}%',)).fetchall()
        else:
            alumnos = conn.execute(
                'SELECT id, nombre, curso, jornada FROM alumnos WHERE activo=1 ORDER BY curso, nombre').fetchall()
        return fa.jsonify({'alumnos': [dict(a) for a in alumnos]})
    finally:
        conn.close()


@rector_bp.route('/<slug>/gestion-academica/promover', methods=['POST'])
def rector_gestion_promover(slug):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify({'ok': False, 'error': 'No autorizado'}), 403
    if not fa.validar_csrf():
        return fa.jsonify({'ok': False, 'error': 'CSRF'}), 400
    data = fa.request.get_json(silent=True) or {}
    origen = data.get('curso_origen', '')
    destino = data.get('curso_destino', '')
    if not origen or not destino:
        return fa.jsonify({'status': 'error', 'error': 'Datos incompletos'}), 400
    conn = fa.conectar(slug)
    try:
        aids = [r['id'] for r in conn.execute('SELECT id FROM alumnos WHERE curso=? AND activo=1', (origen,)).fetchall()]
        if not aids:
            return fa.jsonify({'status': 'error', 'error': 'No hay alumnos en ' + origen})
        placeholders = ','.join('?' * len(aids))
        conn.execute(f'UPDATE alumnos SET curso=? WHERE id IN ({placeholders})', [destino] + aids)
        conn.commit()
        return fa.jsonify({'status': 'ok', 'promovidos': len(aids)})
    finally:
        conn.close()


@rector_bp.route('/<slug>/gestion-academica/trasladar', methods=['POST'])
def rector_gestion_trasladar(slug):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify({'ok': False, 'error': 'No autorizado'}), 403
    if not fa.validar_csrf():
        return fa.jsonify({'ok': False, 'error': 'CSRF'}), 400
    data = fa.request.get_json(silent=True) or {}
    aid = data.get('alumno_id')
    destino = data.get('curso_nuevo', data.get('curso_destino', ''))
    if not aid or not destino:
        return fa.jsonify({'status': 'error', 'error': 'Datos incompletos'}), 400
    conn = fa.conectar(slug)
    try:
        nombre = conn.execute('SELECT nombre FROM alumnos WHERE id=?', (aid,)).fetchone()
        nombre = nombre['nombre'] if nombre else ''
        conn.execute('UPDATE alumnos SET curso=? WHERE id=?', (destino, aid))
        conn.commit()
        return fa.jsonify({'status': 'ok', 'nombre': nombre})
    finally:
        conn.close()


@rector_bp.route('/<slug>/gestion-academica/historial/<int:aid>')
def rector_gestion_historial(slug, aid):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify([]), 403
    conn = fa.conectar(slug)
    try:
        alumno = conn.execute('SELECT id, nombre, curso FROM alumnos WHERE id=?', (aid,)).fetchone()
        notas = conn.execute(
            "SELECT ac.materia, ac.periodo, n.val FROM notas n JOIN actividades ac ON ac.id=n.actividad_id WHERE n.aid=? ORDER BY ac.materia, ac.periodo",
            (aid,)).fetchall()
        historial = [{'curso': n['materia'], 'fecha': n['periodo'], 'estado': str(n['val'])} for n in notas]
        return fa.jsonify({'alumno': dict(alumno) if alumno else {}, 'historial': historial})
    finally:
        conn.close()


@rector_bp.route('/<slug>/matriculas/cupos')
def rector_matriculas_cupos(slug):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify({'cupos': []}), 403
    conn = fa.conectar(slug)
    try:
        cursos = conn.execute(
            'SELECT curso, COUNT(*) as total, GROUP_CONCAT(DISTINCT jornada) as jornada FROM alumnos WHERE activo=1 GROUP BY curso ORDER BY curso').fetchall()
        return fa.jsonify({'cupos': [{'curso': c['curso'], 'jornada': c['jornada'] or '', 'inscritos': c['total']} for c in cursos]})
    finally:
        conn.close()


@rector_bp.route('/<slug>/matriculas')
def rector_matriculas_list(slug):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify({'matriculas': []}), 403
    conn = fa.conectar(slug)
    try:
        alumnos = conn.execute(
            'SELECT id, nombre, curso, jornada, activo FROM alumnos ORDER BY curso, nombre').fetchall()
        result = []
        for a in alumnos:
            estado = 'aprobado' if a['activo'] else 'rechazado'
            result.append({'id': a['id'], 'nombre': a['nombre'], 'curso_solicitado': a['curso'], 'jornada': a['jornada'], 'estado': estado})
        return fa.jsonify({'matriculas': result})
    finally:
        conn.close()


@rector_bp.route('/<slug>/matriculas/crear', methods=['POST'])
def rector_matriculas_crear(slug):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify({'status': 'error', 'error': 'No autorizado'}), 403
    if not fa.validar_csrf():
        return fa.jsonify({'status': 'error', 'error': 'CSRF'}), 400
    data = fa.request.get_json(silent=True) or {}
    nombre = data.get('nombre', '').strip()
    curso = data.get('curso', '').strip()
    jornada = data.get('jornada', '').strip()
    if not nombre or not curso:
        return fa.jsonify({'status': 'error', 'error': 'Nombre y curso requeridos'}), 400
    conn = fa.conectar(slug)
    try:
        conn.execute(
            'INSERT INTO alumnos (nombre, curso, jornada, activo) VALUES (?,?,?,1)',
            (nombre, curso, jornada))
        conn.commit()
        return fa.jsonify({'status': 'ok', 'mensaje': 'Alumno matriculado'})
    finally:
        conn.close()


@rector_bp.route('/<slug>/matriculas/<int:mid>/estado', methods=['POST'])
def rector_matriculas_estado(slug, mid):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify({'status': 'error', 'error': 'No autorizado'}), 403
    if not fa.validar_csrf():
        return fa.jsonify({'status': 'error', 'error': 'CSRF'}), 400
    data = fa.request.get_json(silent=True) or {}
    estado = data.get('estado', 'aprobado')
    activo = 1 if estado == 'aprobado' else 0
    conn = fa.conectar(slug)
    try:
        conn.execute('UPDATE alumnos SET activo=? WHERE id=?', (activo, mid))
        conn.commit()
        return fa.jsonify({'status': 'ok'})
    finally:
        conn.close()


@rector_bp.route('/<slug>/matriculas/<int:mid>/editar', methods=['POST'])
def rector_matriculas_editar(slug, mid):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify({'status': 'error', 'error': 'No autorizado'}), 403
    if not fa.validar_csrf():
        return fa.jsonify({'status': 'error', 'error': 'CSRF'}), 400
    data = fa.request.get_json(silent=True) or {}
    nombre = (data.get('nombre') or '').strip()
    curso = (data.get('curso') or '').strip()
    jornada = (data.get('jornada') or '').strip()
    if not nombre or not curso:
        return fa.jsonify({'status': 'error', 'error': 'Nombre y curso requeridos'}), 400
    conn = fa.conectar(slug)
    try:
        conn.execute('UPDATE alumnos SET nombre=?, curso=?, jornada=? WHERE id=?',
                     (nombre, curso, jornada, mid))
        conn.commit()
        return fa.jsonify({'status': 'ok', 'mensaje': 'Estudiante actualizado'})
    finally:
        conn.close()


@rector_bp.route('/<slug>/tesoreria/facturas')
def rector_tesoreria_list(slug):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify({'facturas': []}), 403
    return fa.jsonify({'facturas': []})


@rector_bp.route('/<slug>/tesoreria/facturas/crear', methods=['POST'])
def rector_tesoreria_crear(slug):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify({'status': 'error', 'error': 'No autorizado'}), 403
    if not fa.validar_csrf():
        return fa.jsonify({'status': 'error', 'error': 'CSRF'}), 400
    return fa.jsonify({'status': 'ok', 'mensaje': 'Funcionalidad en desarrollo'})


@rector_bp.route('/<slug>/tesoreria/facturas/<int:fid>/pagar', methods=['POST'])
def rector_tesoreria_pagar(slug, fid):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify({'status': 'error', 'error': 'No autorizado'}), 403
    if not fa.validar_csrf():
        return fa.jsonify({'status': 'error', 'error': 'CSRF'}), 400
    return fa.jsonify({'status': 'ok', 'mensaje': 'Funcionalidad en desarrollo'})


@rector_bp.route('/<slug>/reportes/tablas')
def rector_reportes_tablas(slug):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify({'tablas': []}), 403
    return fa.jsonify({'tablas': list(COLUMNAS_REPORTES.keys())})


@rector_bp.route('/<slug>/reportes/columnas')
def rector_reportes_columnas(slug):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify({'columnas': []}), 403
    tabla = fa.request.args.get('tabla', '')
    return fa.jsonify({'columnas': COLUMNAS_REPORTES.get(tabla, [])})


@rector_bp.route('/<slug>/reportes/ejecutar', methods=['POST'])
def rector_reportes_ejecutar(slug):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.get_rector(slug):
        return fa.jsonify({'status': 'error', 'error': 'No autorizado'}), 403
    if not fa.validar_csrf():
        return fa.jsonify({'status': 'error', 'error': 'CSRF'}), 400
    data = fa.request.get_json(silent=True) or {}
    tabla = data.get('tabla', '')
    col_names, err = _filtrar_columnas_reportes(
        tabla, data.get('campos', data.get('columnas', [])))
    if err:
        return fa.jsonify({'status': 'error', 'error': err}), 400
    cols_sql = ', '.join(col_names)
    conn = fa.conectar(slug)
    try:
        filas_raw = conn.execute(f'SELECT {cols_sql} FROM {tabla} LIMIT 500').fetchall()
        filas = [[row[c] for c in col_names] for row in filas_raw]
        return fa.jsonify({'columnas': col_names, 'filas': filas, 'total': len(filas)})
    except Exception as e:
        return fa.jsonify({'error': str(e)}), 400
    finally:
        conn.close()


@rector_bp.route('/<slug>/reportes/exportar_excel', methods=['POST'])
def rector_reportes_exportar_excel(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rol, usuario = _institucional(fa, slug)
    if not rol:
        return fa.jsonify({'status': 'error', 'mensaje': 'No autorizado'}), 403
    if not fa.validar_csrf():
        return fa.jsonify({'status': 'error', 'mensaje': 'Error CSRF'}), 403
    data = fa.request.get_json(silent=True) or {}
    tabla = data.get('tabla', '')
    col_names, err = _filtrar_columnas_reportes(
        tabla, data.get('campos', data.get('columnas', [])))
    if err:
        return fa.jsonify({'status': 'error', 'mensaje': err}), 400
    cols_sql = ', '.join(col_names)
    conn = fa.conectar(slug)
    try:
        filas_raw = conn.execute(f'SELECT {cols_sql} FROM {tabla} LIMIT 5000').fetchall()
        filas = [[row[c] for c in col_names] for row in filas_raw]
    except Exception:
        return fa.jsonify({'status': 'error', 'mensaje': 'Error al consultar la tabla.'}), 400
    finally:
        conn.close()
    wb = wb_desde_filas(col_names, filas, tabla[:28])
    fname = f'reporte_{tabla}_{slug}.xlsx'
    return Response(xlsx_bytes(wb), mimetype=MIME_XLSX,
                    headers={'Content-Disposition': f'attachment; filename="{fname}"'})


# ── Excel institucional (rector y directora) ──

@rector_bp.route('/<slug>/institucional/excel')
def institucional_excel(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rol, usuario = _institucional(fa, slug)
    if not rol:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    conn = fa.conectar(slug)
    total_est = conn.execute('SELECT COUNT(*) as c FROM alumnos WHERE activo=1').fetchone()['c']
    total_cursos = len(conn.execute('SELECT DISTINCT curso FROM alumnos WHERE activo=1').fetchall())
    conn.close()
    return fa.render_template('institucional_excel.html', slug=slug, colegio=colegio, rol=rol,
                              **_ctx_institucional(fa, rol, usuario),
                              total_est=total_est, total_cursos=total_cursos,
                              notif_count=fa.notificaciones_no_leidas(slug, rol, usuario['id']))


@rector_bp.route('/<slug>/institucional/importar_estudiantes', methods=['GET'])
def institucional_importar_estudiantes(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rol, usuario = _institucional(fa, slug)
    if not rol:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    colegio = fa.get_colegio(slug)
    conn = fa.conectar(slug)
    cursos = [r['curso'] for r in conn.execute(
        'SELECT DISTINCT curso FROM alumnos WHERE activo=1 ORDER BY curso').fetchall()]
    jornadas = [r['jornada'] for r in conn.execute(
        'SELECT DISTINCT jornada FROM alumnos WHERE activo=1 ORDER BY jornada').fetchall()]
    conn.close()
    return fa.render_template('institucional_importar_estudiantes.html', slug=slug,
                              colegio=colegio, rol=rol, cursos=cursos, jornadas=jornadas,
                              **_ctx_institucional(fa, rol, usuario),
                              notif_count=fa.notificaciones_no_leidas(slug, rol, usuario['id']))


@rector_bp.route('/<slug>/institucional/importar_estudiantes/preview', methods=['POST'])
def institucional_importar_estudiantes_preview(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rol, usuario = _institucional(fa, slug)
    if not rol:
        return fa.jsonify({'status': 'error', 'mensaje': 'No autorizado'}), 403
    if not fa.validar_csrf():
        return fa.jsonify({'status': 'error', 'mensaje': 'Error CSRF'}), 403
    curso = fa.request.form.get('curso', '').strip()
    jornada = fa.request.form.get('jornada', '').strip()
    if not curso or not jornada:
        return fa.jsonify({'status': 'error', 'mensaje': 'Curso y jornada son obligatorios.'}), 400
    if 'archivo' not in fa.request.files:
        return fa.jsonify({'status': 'error', 'mensaje': 'No se envió ningún archivo.'}), 400
    archivo = fa.request.files['archivo']
    if not archivo.filename or not extension_excel_valida(archivo.filename):
        return fa.jsonify({'status': 'error', 'mensaje': 'El archivo debe ser .xlsx.'}), 400
    try:
        headers, filas = leer_workbook(archivo.read())
    except ValueError as e:
        return fa.jsonify({'status': 'error', 'mensaje': str(e)}), 400
    idx_nombre = None
    for i, h in enumerate(headers):
        hl = h.lower()
        if any(k in hl for k in ('nombre', 'name', 'estudiante', 'alumno')):
            if idx_nombre is None:
                idx_nombre = i
    if idx_nombre is None:
        return fa.jsonify({'status': 'error',
                           'mensaje': 'No se encontró una columna "Nombre" en el archivo.'}), 400
    conn = fa.conectar(slug)
    try:
        existentes = conn.execute(
            'SELECT id, nombre FROM alumnos WHERE curso=? AND jornada=? AND activo=1',
            (curso, jornada)).fetchall()
        existentes_by_nombre = {
            r['nombre'].strip().lower(): r for r in existentes if r['nombre']
        }
        preview_rows = []
        seen = set()
        for nro, vals in filas:
            nombre = str(vals[idx_nombre]).strip() if idx_nombre < len(vals) else ''
            errores = []
            if not nombre:
                estado = 'error'
                errores.append('nombre vacío')
            else:
                nl = nombre.lower()
                if nl in seen:
                    estado = 'error'
                    errores.append('duplicado en el archivo')
                elif nl in existentes_by_nombre:
                    estado = 'existe'
                else:
                    estado = 'nuevo'
                    seen.add(nl)
            preview_rows.append({'fila': nro, 'nombre': nombre,
                                 'estado': estado, 'errores': errores})
        nuevos = sum(1 for r in preview_rows if r['estado'] == 'nuevo')
        exist = sum(1 for r in preview_rows if r['estado'] == 'existe')
        errores_count = sum(1 for r in preview_rows if r['estado'] == 'error')
        return fa.jsonify({'status': 'ok', 'curso': curso, 'jornada': jornada,
                           'filas': preview_rows, 'nuevos': nuevos, 'existentes': exist,
                           'errores': errores_count, 'total': len(preview_rows)})
    finally:
        conn.close()


@rector_bp.route('/<slug>/institucional/importar_estudiantes/confirmar', methods=['POST'])
def institucional_importar_estudiantes_confirmar(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rol, usuario = _institucional(fa, slug)
    if not rol:
        return fa.jsonify({'status': 'error', 'mensaje': 'No autorizado'}), 403
    if not fa.validar_csrf():
        return fa.jsonify({'status': 'error', 'mensaje': 'Error CSRF'}), 403
    data_json = fa.request.form.get('data', '')
    if not data_json:
        return fa.jsonify({'status': 'error', 'mensaje': 'No hay datos para guardar.'}), 400
    try:
        data = json.loads(data_json)
    except (json.JSONDecodeError, TypeError):
        return fa.jsonify({'status': 'error', 'mensaje': 'Datos inválidos.'}), 400
    curso = data.get('curso', '').strip()
    jornada = data.get('jornada', '').strip()
    filas = data.get('filas', [])
    if not curso or not jornada:
        return fa.jsonify({'status': 'error', 'mensaje': 'Curso y jornada son obligatorios.'}), 400
    if not filas:
        return fa.jsonify({'status': 'error', 'mensaje': 'No hay filas para importar.'}), 400
    conn = fa.conectar(slug)
    try:
        insertados = 0
        for f in filas:
            if f.get('estado') != 'nuevo':
                continue
            nombre = str(f.get('nombre', '')).strip()
            if not nombre:
                continue
            existe = conn.execute(
                'SELECT id FROM alumnos WHERE nombre=? AND curso=? AND jornada=? AND activo=1',
                (nombre, curso, jornada)).fetchone()
            if existe:
                continue
            cur = conn.execute(
                'INSERT INTO alumnos (nombre, curso, jornada, activo) VALUES (?,?,?,1)',
                (nombre, curso, jornada))
            nuevo_id = cur.lastrowid
            conn.commit()
            fa.audit_log(slug, usuario['id'], 'importar_estudiantes', 'alumnos', nuevo_id,
                         valor_nuevo={'nombre': nombre, 'curso': curso, 'jornada': jornada})
            insertados += 1
        conn.commit()
    except Exception as e:
        conn.close()
        logger.error('Error confirmando importación de estudiantes: %s', e)
        return fa.jsonify({'status': 'error', 'mensaje': 'Error al guardar. Intenta de nuevo.'}), 500
    conn.close()
    return fa.jsonify({'status': 'ok',
                       'mensaje': f'Importación completada. {insertados} estudiante(s) agregado(s).',
                       'insertados': insertados})


@rector_bp.route('/<slug>/institucional/exportar_estudiantes')
def institucional_exportar_estudiantes(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rol, usuario = _institucional(fa, slug)
    if not rol:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    conn = fa.conectar(slug)
    try:
        alumnos = conn.execute(
            'SELECT id, nombre, curso, jornada FROM alumnos '
            'WHERE activo=1 ORDER BY curso, nombre COLLATE NOCASE').fetchall()
    finally:
        conn.close()
    filas = [[a['id'], a['nombre'], a['curso'], a['jornada']] for a in alumnos]
    wb = wb_desde_filas(['ID', 'Nombre', 'Curso', 'Jornada'], filas, 'Estudiantes')
    fname = f'estudiantes_{slug}.xlsx'
    return Response(xlsx_bytes(wb), mimetype=MIME_XLSX,
                    headers={'Content-Disposition': f'attachment; filename="{fname}"'})


@rector_bp.route('/<slug>/institucional/exportar_cursos')
def institucional_exportar_cursos(slug):
    fa = _fa()
    fa.require_colegio(slug)
    rol, usuario = _institucional(fa, slug)
    if not rol:
        return fa.redirect(fa.url_for('auth.login', slug=slug))
    conn = fa.conectar(slug)
    try:
        filas_raw = conn.execute(
            'SELECT curso, jornada, COUNT(*) as n FROM alumnos WHERE activo=1 '
            'GROUP BY curso, jornada ORDER BY curso, jornada').fetchall()
    finally:
        conn.close()
    filas = [[r['curso'], r['jornada'], r['n']] for r in filas_raw]
    wb = wb_desde_filas(['Curso', 'Jornada', 'Estudiantes'], filas, 'Cursos')
    fname = f'cursos_{slug}.xlsx'
    return Response(xlsx_bytes(wb), mimetype=MIME_XLSX,
                    headers={'Content-Disposition': f'attachment; filename="{fname}"'})
