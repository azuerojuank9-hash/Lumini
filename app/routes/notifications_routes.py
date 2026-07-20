from flask import render_template, request, redirect, url_for, jsonify, session
from app.routes import notifications_bp
from app.services.notification_service import (
    get_current_user, list_notificaciones, marcar_leida,
    count_no_leidas, marcar_comunicacion,
)


def _fa():
    import sys
    if 'flask_app' in sys.modules:
        return sys.modules['flask_app']
    import flask_app
    return flask_app


@notifications_bp.route('/<slug>/notificaciones')
def notificaciones(slug):
    fa = _fa()
    fa.require_colegio(slug)
    colegio = fa.get_colegio(slug)
    usuario_tipo, usuario_id = get_current_user(slug)
    if not usuario_id:
        return redirect(url_for('auth.login', slug=slug))
    conn = fa.conectar(slug)
    try:
        notifs = list_notificaciones(conn, usuario_tipo, usuario_id)
    finally:
        conn.close()
    return render_template('notificaciones.html',
                           slug=slug, colegio=colegio,
                           notificaciones=notifs,
                           usuario_tipo=usuario_tipo)


@notifications_bp.route('/<slug>/notificaciones/<int:nid>/leer', methods=['POST'])
def notificacion_leer(slug, nid):
    fa = _fa()
    fa.require_colegio(slug)
    if not fa.validar_csrf():
        return 'Error de seguridad', 400
    usuario_tipo, usuario_id = get_current_user(slug)
    if not usuario_id:
        return jsonify({'ok': False, 'mensaje': 'No autorizado'}), 403
    conn = fa.conectar(slug)
    try:
        marcar_leida(conn, nid, usuario_tipo, usuario_id)
        conn.commit()
    finally:
        conn.close()
    return jsonify({'ok': True})


@notifications_bp.route('/<slug>/notificaciones/contar')
def notificaciones_contar(slug):
    fa = _fa()
    fa.require_colegio(slug)
    usuario_tipo, usuario_id = get_current_user(slug)
    if not usuario_id:
        return jsonify({'count': 0})
    c = fa.notificaciones_no_leidas(slug, usuario_tipo, usuario_id)
    return jsonify({'count': c})


@notifications_bp.route('/<slug>/comunicaciones/<int:cid>/leer', methods=['POST'])
def comunicacion_leer(slug, cid):
    fa = _fa()
    if not fa.validar_csrf():
        return jsonify({'error': 'Error CSRF'}), 403
    fa.require_colegio(slug)
    usuario_tipo, usuario_id = get_current_user(slug)
    if not usuario_id:
        return jsonify({'error': 'No autorizado'}), 403
    conn = fa.conectar(slug)
    try:
        ok = marcar_comunicacion(conn, cid, usuario_tipo, usuario_id, fa.app.logger)
        if not ok:
            return jsonify({'error': 'Error de migración'}), 500
        conn.commit()
    finally:
        conn.close()
    return jsonify({'ok': True})
