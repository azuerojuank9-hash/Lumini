import logging

logger = logging.getLogger(__name__)


def agregar_cursos(conn, profesor_id, materia, jornada, cursos, extra):
    from app.repositories.course_repository import add_cursos_to_profesor
    all_cursos = list(cursos)
    if extra:
        all_cursos += [c.strip() for c in extra.split(',') if c.strip()]
    add_cursos_to_profesor(conn, profesor_id, materia, jornada, all_cursos)


def transferir_curso(conn, from_pid, to_pid, materia, jornada, curso, periodos, jornada_curso):
    from app.repositories.course_repository import (
        transfer_actividades, transfer_evaluaciones,
        copy_asignacion_curso, delete_asignacion_curso
    )
    for p in periodos:
        transfer_actividades(conn, from_pid, to_pid, materia, jornada, curso, p)
        transfer_evaluaciones(conn, from_pid, to_pid, materia, jornada, curso, p, jornada_curso)
    copy_asignacion_curso(conn, to_pid, materia, jornada, curso)
    delete_asignacion_curso(conn, from_pid, materia, jornada, curso)


def archivar_curso(conn, profesor_id, materia, jornada, curso):
    from app.repositories.course_repository import delete_asignacion_curso
    delete_asignacion_curso(conn, profesor_id, materia, jornada, curso)


def get_profesores_destino(conn, materia, jornada, exclude_profesor_id):
    from app.repositories.course_repository import get_profesores_destino
    return get_profesores_destino(conn, materia, jornada, exclude_profesor_id)
