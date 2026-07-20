import logging
from app.repositories.template_repository import (
    get_templates, create_template, get_template_by_id, delete_template,
    get_max_orden, insert_actividad_desde_plantilla
)

logger = logging.getLogger(__name__)


def list_templates(conn, profesor_id):
    rows = get_templates(conn, profesor_id)
    return [{
        'id': t['id'], 'nombre': t['nombre'], 'tipo': t['tipo'],
        'peso': t['peso'], 'descripcion': t['descripcion'], 'creado': t['created_at']
    } for t in rows]


def create(conn, profesor_id, nombre, tipo, peso, descripcion):
    if not nombre:
        return False, 'Nombre requerido'
    create_template(conn, profesor_id, nombre, tipo, peso, descripcion)
    return True, None


def apply_template(conn, profesor_id, tmpl_id, curso, materia, jornada, periodo):
    tmpl = get_template_by_id(conn, tmpl_id, profesor_id)
    if not tmpl:
        return False, 'Plantilla no encontrada'
    max_ord = get_max_orden(conn, materia, jornada, curso, profesor_id)
    insert_actividad_desde_plantilla(conn, profesor_id, materia, jornada, curso, periodo, tmpl['nombre'], tmpl['tipo'], tmpl['peso'], max_ord + 1)
    return True, None


def delete(conn, tid, profesor_id):
    delete_template(conn, tid, profesor_id)
