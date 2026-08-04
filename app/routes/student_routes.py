from flask import redirect, render_template, request, session, url_for

from datetime import datetime

from app.routes import student_bp
from app.services.student_service import (
    get_asistencia_context,
    get_estudiante_context,
    get_horario_context,
    get_notas_context,
    get_observaciones_context,
)


def _fa():
    import sys
    if 'flask_app' in sys.modules:
        return sys.modules['flask_app']
    import flask_app
    return flask_app


@student_bp.route('/<slug>/estudiante')
def vista_estudiante(slug):
    fa = _fa()
    fa.require_colegio(slug)
    if session.get(f'rol_{slug}') != 'estudiante':
        return redirect(url_for('auth.login', slug=slug))
    aid = session.get(f'alumno_id_{slug}')
    colegio = fa.get_colegio(slug)
    num_periodos = int(colegio['num_periodos']) if colegio and colegio['num_periodos'] else 4
    conn = fa.conectar(slug)
    try:
        result = get_estudiante_context(conn, slug, aid)
        if result is None:
            session.pop(f'rol_{slug}', None)
            session.pop(f'alumno_id_{slug}', None)
            return redirect(url_for('auth.login', slug=slug))
        alumno, agenda = result
        periodo = request.args.get('periodo', 1, type=int)
        notas_pm, evals_map, proms_pm, promedio_general = get_notas_context(
            conn, alumno, periodo, fa._promedio_ponderado)
        asist_stats, historial_meses = get_asistencia_context(conn, alumno)
        observaciones = get_observaciones_context(conn, alumno)
        horario_map = get_horario_context(conn, alumno)
        pendientes = fa.comunicaciones_pendientes(slug, 'estudiante', aid)
        hoy = datetime.today().strftime('%Y-%m-%d')
        proximas_evaluaciones = []
        for c in agenda:
            if c['fecha'] and c['fecha'] >= hoy:
                proximas_evaluaciones.append({
                    'titulo': c['titulo'], 'materia': c['materia'], 'fecha': c['fecha'],
                })
        proximas_evaluaciones = proximas_evaluaciones[:5]
        inasistencias = (asist_stats.get('A', 0) + asist_stats.get('E', 0)
                         + asist_stats.get('X', 0) + asist_stats.get('S', 0))
    finally:
        conn.close()
    return render_template('estudiante.html',
                           alumno=alumno, slug=slug, colegio=colegio, agenda=agenda,
                           notas_por_materia=notas_pm, evals_map=evals_map,
                           proms_por_materia=proms_pm,
                           promedio_general=promedio_general,
                           asist_stats=asist_stats, historial_meses=historial_meses,
                           observaciones=observaciones, horario_map=horario_map,
                           comunicaciones_pendientes=pendientes,
                           periodo=periodo, num_periodos=num_periodos,
                           proximas_evaluaciones=proximas_evaluaciones,
                           inasistencias=inasistencias)
