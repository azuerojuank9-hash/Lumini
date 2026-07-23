import logging

logger = logging.getLogger(__name__)


def promedio_simple(notas_actividades):
    if not notas_actividades:
        return None
    vals = [v for v in notas_actividades if v is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 2)


def promedio_ponderado(notas_actividades, evaluacion, autoevaluacion):
    act_prom = promedio_simple(notas_actividades)
    nota_final = 0
    tiene_datos = False
    if act_prom is not None:
        nota_final += act_prom * 0.65
        tiene_datos = True
    if evaluacion is not None:
        nota_final += evaluacion * 0.25
        tiene_datos = True
    if autoevaluacion is not None:
        nota_final += autoevaluacion * 0.10
        tiene_datos = True
    return round(nota_final, 2) if tiene_datos else None


def calcular_stats_estudiante(slug, aid, curso_sel, materia, jornada, periodo, profesor_id):
    from app.repositories.grade_repository import get_notas_for_student
    notas_raw = get_notas_for_student(slug, aid, materia, jornada, curso_sel, periodo, profesor_id)
    vals = [r['val'] for r in notas_raw] if notas_raw else []
    return promedio_simple(vals)


def calcular_nota_final_estudiante(slug, aid, curso_sel, materia, jornada, periodo, profesor_id):
    from app.repositories.grade_repository import get_evaluacion, get_notas_for_student
    notas_raw = get_notas_for_student(slug, aid, materia, jornada, curso_sel, periodo, profesor_id)
    ev = get_evaluacion(slug, aid, profesor_id, materia, jornada, periodo)
    vals = [r['val'] for r in notas_raw] if notas_raw else []
    eval_v = ev['evaluacion'] if ev and ev['evaluacion'] is not None else None
    auto_v = ev['autoevaluacion'] if ev and ev['autoevaluacion'] is not None else None
    return promedio_ponderado(vals, eval_v, auto_v)


def calcular_stats_curso(slug, curso_sel, materia, jornada, periodo, profesor_id):
    from app.repositories.grade_repository import get_actividades_count, get_alumnos_by_curso, get_notas_count
    alumnos = get_alumnos_by_curso(slug, curso_sel, jornada)
    promedios = []
    for a in alumnos:
        p = calcular_stats_estudiante(slug, a['id'], curso_sel, materia, jornada, periodo, profesor_id)
        if p is not None:
            promedios.append(p)
    prom_curso = round(sum(promedios) / len(promedios), 2) if promedios else None
    total_est = len(alumnos)
    act_count = get_actividades_count(slug, materia, jornada, curso_sel, periodo, profesor_id)
    notas_count = get_notas_count(slug, materia, jornada, curso_sel, periodo, profesor_id)
    pend = total_est * act_count - notas_count if total_est and act_count else 0
    return {'promedio_curso': prom_curso, 'notas_pendientes': max(pend, 0)}


def get_notas_mapped(slug, aid_list, materia, jornada, curso, periodo, profesor_id):
    from app.repositories.grade_repository import get_all_evaluaciones_for_curso, get_all_notas_for_curso
    if not aid_list:
        return {}, {}
    notas_all = get_all_notas_for_curso(slug, aid_list, materia, jornada, curso, periodo, profesor_id)
    notas_by_aid = {}
    for r in notas_all:
        notas_by_aid.setdefault(r['aid'], []).append(r)
    evals_all = get_all_evaluaciones_for_curso(slug, aid_list, profesor_id, materia, jornada, periodo)
    evals_by_aid = {r['aid']: r for r in evals_all}
    return notas_by_aid, evals_by_aid
