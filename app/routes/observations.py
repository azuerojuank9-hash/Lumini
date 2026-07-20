import logging
from flask import Blueprint, request, session, jsonify

from app.utils.security import validar_csrf

logger = logging.getLogger(__name__)

observations_bp = Blueprint('observations', __name__)


def _fa():
    import flask_app
    return flask_app


@observations_bp.route('/<slug>/agregar_observacion', methods=['POST'])
def agregar_observacion(slug):
    f = _fa()
    f.require_colegio(slug)
    prof = f.get_profesor(slug)
    if not prof:
        return ('', 403)
    if not validar_csrf():
        return ('Error CSRF', 403)
    jornada, materia = f.get_sesion_jornada_materia(slug)
    texto = request.form.get('texto', '').strip()
    aid = request.form.get('aid', type=int)
    if not texto or aid is None:
        return ('', 400)
    conn = f.conectar(slug)
    cursos_prof = f.get_cursos_profesor(slug, prof['id'], materia, jornada)
    if not cursos_prof:
        conn.close()
        return ('', 403)
    from app.repositories.observation_repository import student_belongs_to_cursos
    if not student_belongs_to_cursos(conn, aid, cursos_prof, jornada):
        conn.close()
        return ('', 403)
    from app.services.observation_service import create_observation
    obs = create_observation(conn, aid, materia, texto)
    conn.commit()
    f.audit_log(slug, prof['id'], 'observacion_creada', 'observaciones', registro_id=obs['id'],
                valor_anterior=None, valor_nuevo={'aid': aid, 'texto': texto})
    conn.close()
    return jsonify({'id': obs['id'], 'materia': obs['materia'],
                    'texto': obs['texto'], 'fecha': obs['fecha']})


@observations_bp.route('/<slug>/editar_observacion/<int:id_o>', methods=['POST'])
def editar_observacion(slug, id_o):
    f = _fa()
    f.require_colegio(slug)
    prof = f.get_profesor(slug)
    if not prof:
        return ('', 403)
    if not validar_csrf():
        return ('Error CSRF', 403)
    jornada, materia = f.get_sesion_jornada_materia(slug)
    texto = request.form.get('texto', '').strip()
    if not texto:
        return ('', 400)
    conn = f.conectar(slug)
    from app.services.observation_service import edit_observation
    result = edit_observation(conn, id_o, materia, texto)
    if not result:
        conn.close()
        return ('', 404)
    conn.commit()
    f.audit_log(slug, prof['id'], 'observacion_editada', 'observaciones', registro_id=id_o,
                valor_anterior={'texto': result['old_text']}, valor_nuevo={'texto': texto})
    conn.close()
    return jsonify({'id': result['id'], 'aid': result['aid'], 'materia': result['materia'],
                    'texto': texto, 'fecha': result['fecha']})


@observations_bp.route('/<slug>/borrar_observacion/<int:id_o>', methods=['POST'])
def borrar_observacion(slug, id_o):
    f = _fa()
    f.require_colegio(slug)
    prof = f.get_profesor(slug)
    if not prof:
        return ('', 403)
    if not validar_csrf():
        return ('Error CSRF', 403)
    jornada, materia = f.get_sesion_jornada_materia(slug)
    conn = f.conectar(slug)
    from app.services.observation_service import delete_observation
    deleted = delete_observation(conn, id_o, materia)
    if deleted:
        conn.commit()
        f.audit_log(slug, prof['id'], 'observacion_eliminada', 'observaciones', registro_id=id_o,
                    valor_anterior={'aid': deleted['aid'], 'texto': deleted['texto']}, valor_nuevo=None)
    conn.close()
    return jsonify({'ok': True})
