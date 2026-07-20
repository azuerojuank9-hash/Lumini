import logging

logger = logging.getLogger(__name__)


def register_student(conn, nombre, curso, jornada):
    from app.repositories.student_repository import create_student, renumber_students
    create_student(conn, nombre, curso, jornada)
    renumber_students(conn, curso, jornada)


def archive_student_action(conn, aid):
    from app.repositories.student_repository import archive_student
    archive_student(conn, aid)


def reactivate_student_action(conn, aid):
    from app.repositories.student_repository import reactivate_student
    reactivate_student(conn, aid)


def delete_student_action(conn, aid):
    from app.repositories.student_repository import delete_student
    delete_student(conn, aid)


def build_archivados_context(conn, jornada, mis_cursos, curso_sel):
    from app.repositories.student_repository import (
        get_archived_students, get_archived_profesores,
        get_active_profesores, get_asignaciones_materia,
        get_asignaciones_curso, get_other_active_profesores_by_mat_jor
    )
    alumnos_arch = []
    if curso_sel:
        alumnos_arch = get_archived_students(conn, curso_sel, jornada)
    profs_arch = get_archived_profesores(conn)
    profs_raw = get_active_profesores(conn)
    all_mat = get_asignaciones_materia(conn)
    all_cur = get_asignaciones_curso(conn)
    mat_by_prof = {}
    for r in all_mat:
        mat_by_prof.setdefault(r['profesor_id'], []).append(r)
    cur_by_prof_mat_jor = {}
    for r in all_cur:
        cur_by_prof_mat_jor[(r['profesor_id'], r['materia'], r['jornada'])] = r['curso']
    other_profs_raw = get_other_active_profesores_by_mat_jor(conn)
    other_by_mat_jor = {}
    for r in other_profs_raw:
        other_by_mat_jor.setdefault((r['materia'], r['jornada']), []).append(r)
    profesores_activos = []
    for p in profs_raw:
        mjs = mat_by_prof.get(p['id'], [])
        cursos_info = []
        for mj in mjs:
            curso_val = cur_by_prof_mat_jor.get((p['id'], mj['materia'], mj['jornada']))
            if curso_val:
                cursos_info.append({'curso': curso_val, 'materia': mj['materia'], 'jornada': mj['jornada']})
        otros_profesores = []
        seen_otros = set()
        for mj in mjs:
            for o in other_by_mat_jor.get((mj['materia'], mj['jornada']), []):
                if o['id'] == p['id']:
                    continue
                entry_key = (o['id'], o['materia'], o['jornada'])
                if entry_key not in seen_otros:
                    seen_otros.add(entry_key)
                    entry = {'id': o['id'], 'nombre': o['nombre'], 'materia': o['materia'], 'jornada': o['jornada']}
                    if entry not in otros_profesores:
                        otros_profesores.append(entry)
        profesores_activos.append({
            'id': p['id'], 'nombre': p['nombre'], 'usuario': p['usuario'],
            'email': p['email'] or '',
            'materias_jornadas': [dict(mj) for mj in mjs],
            'cursos_info': cursos_info,
            'otros_profesores': otros_profesores,
        })
    return {
        'alumnos_arch': alumnos_arch,
        'profs_arch': profs_arch,
        'profesores_activos': profesores_activos,
    }


def get_estudiante_context(conn, slug, aid):
    from app.repositories.student_repository import (
        get_alumno, get_compromisos_curso, get_notas_estudiante,
        get_evaluaciones_estudiante, get_asistencia_estudiante,
        get_observaciones_estudiante, get_horario_curso,
    )
    alumno = get_alumno(conn, aid)
    if not alumno:
        return None
    agenda = get_compromisos_curso(conn, alumno['curso'], alumno['jornada'])
    return alumno, agenda


def get_notas_context(conn, alumno, periodo, _promedio_ponderado):
    from app.repositories.student_repository import (
        get_notas_estudiante, get_evaluaciones_estudiante,
    )
    notas_raw = get_notas_estudiante(conn, alumno['id'], alumno['curso'], alumno['jornada'], periodo)
    evals_raw = get_evaluaciones_estudiante(conn, alumno['id'], periodo)
    evals_map = {e['materia']: dict(e) for e in evals_raw}
    notas_pm = {}
    for nr in notas_raw:
        notas_pm.setdefault(nr['materia'], []).append({'actividad': nr['act_nombre'], 'val': nr['val']})
    for mat in evals_map:
        if mat not in notas_pm:
            notas_pm[mat] = []
    proms_pm = {}
    todos_finales = []
    for mat, notas in notas_pm.items():
        notas_vals = [n['val'] for n in notas]
        ev = evals_map.get(mat, {})
        eval_v = ev.get('evaluacion') if ev.get('evaluacion') is not None else None
        auto_v = ev.get('autoevaluacion') if ev.get('autoevaluacion') is not None else None
        prom = _promedio_ponderado(notas_vals, eval_v, auto_v)
        proms_pm[mat] = prom
        if prom is not None:
            todos_finales.append(prom)
    promedio_general = round(sum(todos_finales) / len(todos_finales), 2) if todos_finales else None
    return notas_pm, evals_map, proms_pm, promedio_general


def get_asistencia_context(conn, alumno):
    from app.repositories.student_repository import get_asistencia_estudiante
    from app.services.notification_service import ESTADOS_ASISTENCIA, MESES
    asist_raw = get_asistencia_estudiante(conn, alumno['id'])
    asist_stats = {k: 0 for k in ESTADOS_ASISTENCIA}
    asist_stats['total'] = 0
    historial_meses = {}
    for h in asist_raw:
        asist_stats[h['estado']] = asist_stats.get(h['estado'], 0) + 1
        asist_stats['total'] += 1
        if h['fecha']:
            p = h['fecha'].split('-')
            if len(p) >= 2:
                label = f"{MESES.get(p[1], p[1])} {p[0]}"
                historial_meses.setdefault(label, []).append({
                    'fecha': h['fecha'], 'estado': h['estado'],
                    'observacion': h['observacion'] or ''
                })
    total = asist_stats['total']
    asist_stats['porcentaje_asistencia'] = round(asist_stats['P'] / total * 100, 1) if total else 0
    asist_stats['porcentaje_inasistencia'] = round(
        (asist_stats['A'] + asist_stats['E'] + asist_stats['X'] + asist_stats['S']) / total * 100, 1
    ) if total else 0
    asist_stats['porcentaje_tardanzas'] = round(asist_stats['T'] / total * 100, 1) if total else 0
    return asist_stats, historial_meses


def get_observaciones_context(conn, alumno):
    from app.repositories.student_repository import get_observaciones_estudiante
    return get_observaciones_estudiante(conn, alumno['id'])


def get_horario_context(conn, alumno):
    from app.repositories.student_repository import get_horario_curso
    horario_raw = get_horario_curso(conn, alumno['curso'], alumno['jornada'])
    horario_map = {
        f"{r['dia']}_{r['franja']}": {'num': r['num'], 'materia': r['materia'], 'profesor': r['profesor']}
        for r in horario_raw}
    return horario_map
