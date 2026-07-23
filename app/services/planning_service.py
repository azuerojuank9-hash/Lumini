import logging

from app.repositories.planning_repository import copiar_actividad, get_actividades_origin, get_next_orden

logger = logging.getLogger(__name__)


def copy_planning(conn, profesor_id, materia, jornada, origen_curso, destino_cursos):
    acts = get_actividades_origin(conn, materia, jornada, origen_curso, profesor_id)
    count = 0
    for dest in destino_cursos:
        for a in acts:
            orden = get_next_orden(conn, materia, jornada, dest, profesor_id)
            copiar_actividad(conn, profesor_id, materia, jornada, dest, a, orden)
            count += 1
    conn.commit()
    return count
