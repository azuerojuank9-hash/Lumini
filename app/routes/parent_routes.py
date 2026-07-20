from flask import jsonify, session
from app.routes import parent_bp
from app.services.parent_service import ParentService


def _fa():
    import sys
    if 'flask_app' in sys.modules:
        return sys.modules['flask_app']
    import flask_app
    return flask_app


@parent_bp.route('/<slug>/portal/dashboard')
def portal_padre_dashboard(slug):
    fa = _fa()
    fa.require_colegio(slug)
    pid = session.get(f'padre_id_{slug}')
    if not pid:
        return jsonify({'error': 'No autorizado'}), 403
    conn = fa.conectar(slug)
    try:
        resultado = ParentService.get_dashboard_data(conn, pid)
        return jsonify({'hijos': resultado})
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
        actividades = ParentService.get_notas_alumno(conn, alumno_id)
        return jsonify({'actividades': actividades})
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
