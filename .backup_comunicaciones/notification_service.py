import logging

from app.repositories.notification_repository import (
    marcar_comunicacion_leida,
    marcar_notificacion_leida,
)
from app.repositories.notification_repository import (
    get_notificaciones as repo_get_notificaciones,
)

logger = logging.getLogger(__name__)

MESES = {'01': 'Ene', '02': 'Feb', '03': 'Mar', '04': 'Abr', '05': 'May', '06': 'Jun',
         '07': 'Jul', '08': 'Ago', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dic'}

ESTADOS_ASISTENCIA = {'P': 'Presente', 'A': 'Ausente', 'T': 'Tardanza', 'E': 'Excusa', 'X': 'Permiso', 'S': 'Salida anticipada'}


def get_current_user(slug):
    from flask import session

    from app.infra.helpers import get_directora, get_profesor, get_rector
    usuario_tipo = None
    usuario_id = None
    rector = get_rector(slug)
    if rector:
        usuario_tipo, usuario_id = 'rector', rector['id']
    if not usuario_id:
        prof = get_profesor(slug)
        if prof:
            usuario_tipo, usuario_id = 'profesor', prof['id']
    if not usuario_id:
        directora = get_directora(slug)
        if directora:
            usuario_tipo, usuario_id = 'directora', directora['id']
    if not usuario_id:
        aid = session.get(f'alumno_id_{slug}')
        if aid:
            usuario_tipo, usuario_id = 'estudiante', aid
    return usuario_tipo, usuario_id


def list_notificaciones(conn, usuario_tipo, usuario_id):
    return repo_get_notificaciones(conn, usuario_tipo, usuario_id)


def marcar_leida(conn, nid, usuario_tipo, usuario_id):
    marcar_notificacion_leida(conn, nid, usuario_tipo, usuario_id)


def marcar_comunicacion(conn, cid, usuario_tipo, usuario_id, logger=None):
    from app.repositories.notification_repository import add_columna_leido, get_columna_leido_exists
    if not get_columna_leido_exists(conn):
        add_columna_leido(conn)
    marcar_comunicacion_leida(conn, cid, usuario_tipo, usuario_id)
    return True
