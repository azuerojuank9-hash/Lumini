from flask import jsonify, render_template, request, session

from app.routes import parent_bp
from app.services.parent_service import ParentService


def _fa():
    import sys
    if 'flask_app' in sys.modules:
        return sys.modules['flask_app']
    import flask_app
    return flask_app


def _is_json_request():
    accept = request.headers.get('Accept', '')
    return 'text/html' not in accept or request.args.get('json') is not None


@parent_bp.route('/<slug>/portal/dashboard')
def portal_padre_dashboard(slug):
    fa = _fa()
    fa.require_colegio(slug)
    pid = session.get(f'padre_id_{slug}')
    if not pid:
        if _is_json_request():
            return jsonify({'error': 'No autorizado'}), 403
        return render_template('portal_padre.html', slug=slug, colegio=fa.get_colegio(slug), step='login')
    conn = fa.conectar(slug)
    try:
        resultado = ParentService.get_dashboard_data(conn, pid)
        if _is_json_request():
            return jsonify({'hijos': resultado})
        return render_template('portal_padre.html', slug=slug, colegio=fa.get_colegio(slug),
                               step='dashboard', hijos=resultado,
                               padre=conn.execute('SELECT * FROM padres WHERE id=?', (pid,)).fetchone())
    finally:
        conn.close()


@parent_bp.route('/<slug>/portal/notas/<int:alumno_id>')
def portal_padre_notas(slug, alumno_id):
    fa = _fa()
    fa.require_colegio(slug)
    pid = session.get(f'padre_id_{slug}')
    if not pid:
        return jsonify({'error': 'No autorizado'}), 403
    conn = fa.conectar(slug)
    try:
        if not ParentService.verificar_relacion(conn, pid, alumno_id):
            return jsonify({'error': 'No autorizado'}), 403
        return jsonify(ParentService.get_notas_alumno(conn, alumno_id))
    finally:
        conn.close()


@parent_bp.route('/<slug>/portal/asistencia/<int:alumno_id>')
def portal_padre_asistencia(slug, alumno_id):
    fa = _fa()
    fa.require_colegio(slug)
    pid = session.get(f'padre_id_{slug}')
    if not pid:
        return jsonify({'error': 'No autorizado'}), 403
    conn = fa.conectar(slug)
    try:
        if not ParentService.verificar_relacion(conn, pid, alumno_id):
            return jsonify({'error': 'No autorizado'}), 403
        asistencia = ParentService.get_asistencia_alumno(conn, alumno_id)
        return jsonify({'asistencia': asistencia})
    finally:
        conn.close()


@parent_bp.route('/<slug>/portal/comunicados')
def portal_padre_comms(slug):
    fa = _fa()
    fa.require_colegio(slug)
    pid = session.get(f'padre_id_{slug}')
    if not pid:
        return jsonify({'error': 'No autorizado'}), 403
    conn = fa.conectar(slug)
    try:
        comunicados = ParentService.get_comunicados(conn, pid)
        return jsonify({'comunicados': comunicados})
    finally:
        conn.close()


@parent_bp.route('/<slug>/portal/horario/<int:alumno_id>')
def portal_padre_horario(slug, alumno_id):
    fa = _fa()
    fa.require_colegio(slug)
    pid = session.get(f'padre_id_{slug}')
    if not pid:
        return jsonify({'error': 'No autorizado'}), 403
    conn = fa.conectar(slug)
    try:
        if not ParentService.verificar_relacion(conn, pid, alumno_id):
            return jsonify({'error': 'No autorizado'}), 403
        horario = ParentService.get_horario_alumno(conn, alumno_id)
        return jsonify({'horario': horario})
    finally:
        conn.close()


@parent_bp.route('/<slug>/portal/observaciones/<int:alumno_id>')
def portal_padre_observaciones(slug, alumno_id):
    fa = _fa()
    fa.require_colegio(slug)
    pid = session.get(f'padre_id_{slug}')
    if not pid:
        return jsonify({'error': 'No autorizado'}), 403
    conn = fa.conectar(slug)
    try:
        if not ParentService.verificar_relacion(conn, pid, alumno_id):
            return jsonify({'error': 'No autorizado'}), 403
        observaciones = ParentService.get_observaciones_alumno(conn, alumno_id)
        return jsonify({'observaciones': observaciones})
    finally:
        conn.close()


@parent_bp.route('/<slug>/portal/historial/<int:alumno_id>')
def portal_padre_historial(slug, alumno_id):
    fa = _fa()
    fa.require_colegio(slug)
    pid = session.get(f'padre_id_{slug}')
    if not pid:
        return jsonify({'error': 'No autorizado'}), 403
    conn = fa.conectar(slug)
    try:
        if not ParentService.verificar_relacion(conn, pid, alumno_id):
            return jsonify({'error': 'No autorizado'}), 403
        historial = ParentService.get_historial_alumno(conn, alumno_id)
        return jsonify({'historial': historial})
    finally:
        conn.close()
