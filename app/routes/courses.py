import logging
from flask import Blueprint, request, redirect, url_for, render_template

from app.utils.security import validar_csrf

logger = logging.getLogger(__name__)

courses_bp = Blueprint('courses', __name__)


def _fa():
    import flask_app
    return flask_app


@courses_bp.route('/<slug>/agregar_cursos', methods=['POST'])
def agregar_cursos(slug):
    if not validar_csrf():
        return 'Error de seguridad', 400
    f = _fa()
    f.require_colegio(slug)
    prof = f.get_profesor(slug)
    if not prof:
        return redirect(url_for('auth.login', slug=slug))
    jornada, materia = f.get_sesion_jornada_materia(slug)
    cursos = request.form.getlist('cursos')
    extra = request.form.get('cursos_extra', '').strip()
    conn = f.conectar(slug)
    from app.services.course_service import agregar_cursos
    agregar_cursos(conn, prof['id'], materia, jornada, cursos, extra)
    conn.commit()
    conn.close()
    return redirect(url_for('auth.cambiar_password', slug=slug))


@courses_bp.route('/<slug>/quitar_curso/<curso>', methods=['POST'])
def quitar_curso(slug, curso):
    if not validar_csrf():
        return redirect(url_for('auth.cambiar_password', slug=slug))
    f = _fa()
    f.require_colegio(slug)
    prof = f.get_profesor(slug)
    if not prof:
        return redirect(url_for('auth.login', slug=slug))
    jornada, materia = f.get_sesion_jornada_materia(slug)
    conn = f.conectar(slug)
    from app.repositories.course_repository import remove_curso_from_profesor
    remove_curso_from_profesor(conn, prof['id'], materia, jornada, curso)
    conn.commit()
    conn.close()
    return redirect(url_for('auth.cambiar_password', slug=slug))


@courses_bp.route('/<slug>/transferir_curso', methods=['GET', 'POST'])
def transferir_curso(slug):
    f = _fa()
    f.require_colegio(slug)
    prof = f.get_profesor(slug)
    if not prof:
        return redirect(url_for('auth.login', slug=slug))
    jornada, materia = f.get_sesion_jornada_materia(slug)
    if not jornada or not materia:
        return redirect(url_for('teacher.seleccionar_jornada', slug=slug))
    colegio = f.get_colegio(slug)
    error = exito = None
    mis_cursos = f.get_cursos_profesor(slug, prof['id'], materia, jornada)
    conn = f.conectar(slug)
    from app.services.course_service import get_profesores_destino
    profesores_destino = get_profesores_destino(conn, materia, jornada, prof['id'])
    num_periodos = int(colegio['num_periodos']) if colegio and colegio['num_periodos'] else 4
    conn.close()

    if request.method == 'POST':
        if not validar_csrf():
            error = 'Error de seguridad.'
        else:
            accion = request.form.get('accion', '')
            curso_transferir = request.form.get('curso', '').strip()
            periodos_str = request.form.get('periodos', '')
            periodos = [p for p in periodos_str.split(',') if p.strip()]
            if not curso_transferir:
                error = 'Selecciona un curso.'
            elif not periodos:
                error = 'Selecciona al menos un periodo.'
            elif curso_transferir not in mis_cursos:
                error = 'Ese curso no te pertenece.'
            else:
                conn = f.conectar(slug)
                if accion == 'transferir':
                    prof_destino_id = request.form.get('profesor_destino_id', type=int)
                    if not prof_destino_id:
                        error = 'Selecciona un profesor destino.'
                        conn.close()
                    else:
                        from app.services.course_service import transferir_curso
                        periodos_int = [int(p) for p in periodos]
                        transferir_curso(conn, prof['id'], prof_destino_id, materia, jornada,
                                         curso_transferir, periodos_int, jornada)
                        conn.commit()
                        conn.close()
                        exito = f'\u2705 Curso {curso_transferir} transferido correctamente.'
                        mis_cursos = f.get_cursos_profesor(slug, prof['id'], materia, jornada)
                elif accion == 'archivar_curso':
                    from app.services.course_service import archivar_curso
                    archivar_curso(conn, prof['id'], materia, jornada, curso_transferir)
                    conn.commit()
                    conn.close()
                    exito = f'\u2705 Curso {curso_transferir} archivado.'
                    mis_cursos = f.get_cursos_profesor(slug, prof['id'], materia, jornada)
                else:
                    conn.close()
                    error = 'Acci\u00f3n no reconocida.'

    return render_template('transferir_curso.html',
                           slug=slug, colegio=colegio, profesor=prof,
                           mis_cursos=mis_cursos, profesores_destino=profesores_destino,
                           error=error, exito=exito, materia=materia, jornada=jornada,
                           num_periodos=num_periodos)
