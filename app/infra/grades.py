import logging

logger = logging.getLogger(__name__)


def _promedio_simple(notas_actividades):
    if not notas_actividades:
        return None
    vals = [v for v in notas_actividades if v is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 2)


def _promedio_ponderado(notas_actividades, evaluacion, autoevaluacion):
    act_prom = _promedio_simple(notas_actividades)
    logger.debug('_promedio_ponderado: act_prom=%s evaluacion=%s autoevaluacion=%s', act_prom, evaluacion, autoevaluacion)
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
    resultado = round(nota_final, 2) if tiene_datos else None
    logger.debug('_promedio_ponderado: resultado=%s', resultado)
    return resultado


def calcular_stats_estudiante(conn, slug, aid, curso_sel, materia, jornada, periodo, profesor_id):
    notas_raw = conn.execute(
        '''SELECT n.val FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
           WHERE n.aid=? AND ac.materia=? AND ac.jornada=? AND ac.curso=?
           AND COALESCE(ac.periodo,1)=? AND ac.profesor_id=?''',
        (aid, materia, jornada, curso_sel, periodo, profesor_id)).fetchall()
    vals = [r['val'] for r in notas_raw] if notas_raw else []
    return _promedio_simple(vals)


def calcular_nota_final_estudiante(conn, slug, aid, curso_sel, materia, jornada, periodo, profesor_id):
    notas_raw = conn.execute(
        '''SELECT n.val FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
           WHERE n.aid=? AND ac.materia=? AND ac.jornada=? AND ac.curso=?
           AND COALESCE(ac.periodo,1)=? AND ac.profesor_id=?''',
        (aid, materia, jornada, curso_sel, periodo, profesor_id)).fetchall()
    ev = conn.execute(
        '''SELECT evaluacion, autoevaluacion FROM evaluaciones
           WHERE aid=? AND materia=? AND jornada=? AND COALESCE(periodo,1)=?''',
        (aid, materia, jornada, periodo)).fetchone()
    vals = [r['val'] for r in notas_raw] if notas_raw else []
    eval_v   = ev['evaluacion']     if ev and ev['evaluacion']     is not None else None
    auto_v   = ev['autoevaluacion'] if ev and ev['autoevaluacion'] is not None else None
    return _promedio_ponderado(vals, eval_v, auto_v)


def calcular_stats_curso(conn, slug, curso_sel, materia, jornada, periodo, profesor_id):
    alumnos = conn.execute(
        'SELECT id FROM alumnos WHERE curso=? AND jornada=? AND activo=1',
        (curso_sel, jornada)).fetchall()
    promedios = []
    for a in alumnos:
        p = calcular_stats_estudiante(conn, slug, a['id'], curso_sel, materia, jornada, periodo, profesor_id)
        if p is not None:
            promedios.append(p)
    prom_curso = round(sum(promedios) / len(promedios), 2) if promedios else None
    total_est = len(alumnos)
    act_ids = conn.execute(
        '''SELECT id FROM actividades WHERE materia=? AND jornada=? AND curso=?
           AND COALESCE(periodo,1)=? AND profesor_id=?''',
        (materia, jornada, curso_sel, periodo, profesor_id)).fetchall()
    act_count = len(act_ids)
    notas_count = conn.execute(
        '''SELECT COUNT(*) as c FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
           WHERE ac.materia=? AND ac.jornada=? AND ac.curso=? AND COALESCE(ac.periodo,1)=?
           AND ac.profesor_id=?''',
        (materia, jornada, curso_sel, periodo, profesor_id)).fetchone()['c']
    pend = total_est * act_count - notas_count if total_est and act_count else 0
    return {'promedio_curso': prom_curso, 'notas_pendientes': max(pend, 0)}
