import os
from flask import Blueprint, jsonify, request, send_file
from app.services.file_service import get_archivo, eliminar_archivo_db, eliminar_archivo_fisico, guardar_archivo_mensaje

files_bp = Blueprint('files', __name__)


def _fa():
    import flask_app as fa
    return fa


@files_bp.route('/<slug>/api/canales/<int:cid>/archivos/subir', methods=['POST'])
def api_canales_subir_archivos(slug, cid):
    fa = _fa()
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'error': 'CSRF'}), 403
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 401
    if 'archivo' not in request.files:
        return jsonify({'ok': False, 'error': 'No hay archivo'}), 400
    f = request.files['archivo']
    if not f.filename:
        return jsonify({'ok': False, 'error': 'Archivo vacío'}), 400
    fid, err = guardar_archivo_mensaje(slug, cid, f, tipo, uid, fa.app.root_path)
    if err:
        return jsonify({'ok': False, 'error': err}), 400
    return jsonify({'ok': True, 'archivo_id': fid})


@files_bp.route('/<slug>/api/archivos/<int:fid>/descargar')
def api_archivo_descargar(slug, fid):
    fa = _fa()
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return 'No autorizado', 401
    conn = fa.conectar(slug)
    arch = get_archivo(conn, fid)
    conn.close()
    if not arch:
        return 'No encontrado', 404
    ruta = os.path.join(fa.app.root_path, 'static', 'uploads', slug, arch['nombre_archivo'])
    if not os.path.exists(ruta):
        return 'No encontrado', 404
    return send_file(ruta, mimetype=arch['tipo_mime'], as_attachment=True,
                     download_name=arch['nombre_original'])


@files_bp.route('/<slug>/api/archivos/<int:fid>/previsualizar')
def api_archivo_previsualizar(slug, fid):
    fa = _fa()
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return 'No autorizado', 401
    conn = fa.conectar(slug)
    arch = get_archivo(conn, fid)
    conn.close()
    if not arch:
        return 'No encontrado', 404
    ruta = os.path.join(fa.app.root_path, 'static', 'uploads', slug, arch['nombre_archivo'])
    if not os.path.exists(ruta):
        return 'No encontrado', 404
    if arch['es_imagen']:
        return send_file(ruta, mimetype=arch['tipo_mime'])
    if arch['tipo_mime'] == 'application/pdf':
        return send_file(ruta, mimetype='application/pdf')
    return jsonify({'ok': False, 'error': 'Vista previa no disponible'})


@files_bp.route('/<slug>/api/archivos/<int:fid>/eliminar', methods=['DELETE', 'POST'])
def api_archivo_eliminar(slug, fid):
    fa = _fa()
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'error': 'CSRF'}), 403
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 401
    conn = fa.conectar(slug)
    arch = get_archivo(conn, fid)
    if not arch:
        conn.close()
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404
    if arch['usuario_tipo'] != tipo or arch['usuario_id'] != uid:
        if tipo != 'rector':
            conn.close()
            return jsonify({'ok': False, 'error': 'No puedes eliminar este archivo'}), 403
    eliminar_archivo_db(conn, fid)
    conn.commit()
    fa.audit_log(slug, uid, 'delete', 'mensajes_archivos', fid,
                 valor_anterior={'nombre_original': arch['nombre_original']})
    conn.close()
    ruta = os.path.join(fa.app.root_path, 'static', 'uploads', slug, arch['nombre_archivo'])
    eliminar_archivo_fisico(ruta)
    return jsonify({'ok': True})
