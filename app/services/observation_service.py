import logging

logger = logging.getLogger(__name__)


def verify_student_access(conn, aid, cursos_prof, jornada):
    from app.repositories.observation_repository import student_belongs_to_cursos
    return student_belongs_to_cursos(conn, aid, cursos_prof, jornada)


def create_observation(conn, aid, materia, texto):
    from app.repositories.observation_repository import create_observation
    return create_observation(conn, aid, materia, texto)


def edit_observation(conn, id_o, materia, texto):
    from app.repositories.observation_repository import get_observation, update_observation
    obs = get_observation(conn, id_o, materia)
    if not obs:
        return None
    old_text = obs['texto']
    update_observation(conn, id_o, texto)
    return {'id': obs['id'], 'aid': obs['aid'], 'materia': obs['materia'],
            'old_text': old_text, 'fecha': obs['fecha']}


def delete_observation(conn, id_o, materia):
    from app.repositories.observation_repository import delete_observation, get_observation_by_id
    obs = get_observation_by_id(conn, id_o)
    if obs and obs['materia'] == materia:
        delete_observation(conn, id_o)
        return {'aid': obs['aid'], 'texto': obs['texto']}
    return None
