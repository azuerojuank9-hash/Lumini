from collections import Counter

from app.infra.database import config_get
from app.infra.grades import _promedio_ponderado


def _estadisticas_desc(vals):
    if not vals:
        return None
    clean = [v for v in vals if v is not None]
    if not clean:
        return None
    n = len(clean)
    s = sorted(clean)
    media = round(sum(clean) / n, 2)
    if n % 2 == 0:
        mediana = (s[n // 2 - 1] + s[n // 2]) / 2
    else:
        mediana = s[n // 2]
    freq = Counter(clean)
    max_f = max(freq.values())
    moda = [k for k, v in freq.items() if v == max_f]
    moda = moda[0] if len(moda) == 1 else None
    var = sum((x - media) ** 2 for x in clean) / n
    desv = round(var ** 0.5, 2)
    maximo = max(clean)
    minimo = min(clean)

    def pct(p):
        idx = max(0, min(n - 1, round(n * p / 100)))
        return s[idx]
    q1 = pct(25)
    q2 = mediana
    q3 = pct(75)
    return {
        'media': round(media, 2), 'mediana': round(mediana, 2), 'moda': round(moda, 2) if moda is not None else None,
        'desviacion': desv, 'maximo': round(maximo, 2), 'minimo': round(minimo, 2),
        'q1': round(q1, 2), 'q2': round(q2, 2), 'q3': round(q3, 2),
        'p10': round(pct(10), 2), 'p90': round(pct(90), 2),
    }


def _dashboard_student_grades(conn, slug, profesor_id, materia, jornada, curso=None, periodo=None):
    if curso:
        alumnos = conn.execute(
            'SELECT id, nombre, curso FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre',
            (curso, jornada)).fetchall()
    else:
        alumnos = conn.execute(
            '''SELECT a.id, a.nombre, a.curso FROM alumnos a
               JOIN asignaciones_curso ac ON ac.curso=a.curso
               WHERE ac.profesor_id=? AND ac.materia=? AND ac.jornada=?
                 AND a.jornada=? AND a.activo=1 ORDER BY a.nombre''',
            (profesor_id, materia, jornada, jornada)).fetchall()
    if not alumnos:
        return []
    aids = [a['id'] for a in alumnos]
    ph = ','.join('?' * len(aids))
    notas_rows = conn.execute(
        f'''SELECT n.aid, n.val FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
            WHERE n.aid IN ({ph}) AND ac.profesor_id=? AND ac.materia=? AND ac.jornada=?
            AND (? IS NULL OR ac.periodo=?)''',
        (*aids, profesor_id, materia, jornada, periodo, periodo)).fetchall()
    notas_by_aid = {}
    for r in notas_rows:
        notas_by_aid.setdefault(r['aid'], []).append(r['val'])
    ev_rows = conn.execute(
        f'''SELECT aid, evaluacion, autoevaluacion FROM evaluaciones
            WHERE aid IN ({ph}) AND profesor_id=? AND materia=? AND jornada=?
            AND (? IS NULL OR periodo=?)''',
        (*aids, profesor_id, materia, jornada, periodo, periodo)).fetchall()
    ev_by_aid = {r['aid']: r for r in ev_rows}
    res = []
    for a in alumnos:
        vals = notas_by_aid.get(a['id'], [])
        ev = ev_by_aid.get(a['id'])
        ev_v = ev['evaluacion'] if ev and ev['evaluacion'] is not None else None
        au_v = ev['autoevaluacion'] if ev and ev['autoevaluacion'] is not None else None
        final = _promedio_ponderado(vals, ev_v, au_v)
        res.append({'id': a['id'], 'nombre': a['nombre'], 'curso': a['curso'],
                     'nota_final': final, 'actividades': vals})
    return res


def _dashboard_profesor_data(conn, slug, prof, curso=None, materia=None, jornada=None, periodo=None):
    m = materia or ''
    j = jornada or ''
    cursos_q = [curso] if curso else [r['curso'] for r in conn.execute(
        'SELECT DISTINCT curso FROM asignaciones_curso WHERE profesor_id=? AND materia=? AND jornada=?',
        (prof['id'], m, j)).fetchall()]
    scoped = lambda c: conn.execute(
        'SELECT id, nombre, curso FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre',
        (c, j)).fetchall()
    all_alumnos = []
    for c in cursos_q:
        all_alumnos.extend(scoped(c))
    aids = [a['id'] for a in all_alumnos]
    total_estudiantes = len(all_alumnos)
    total_actividades = conn.execute(
        'SELECT COUNT(*) FROM actividades WHERE profesor_id=? AND materia=? AND jornada=? AND (? IS NULL OR curso=?) AND (? IS NULL OR periodo=?)',
        (prof['id'], m, j, curso, curso, periodo, periodo)).fetchone()[0]
    calificadas = conn.execute(
        '''SELECT COUNT(*) FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
           WHERE ac.profesor_id=? AND ac.materia=? AND ac.jornada=?
           AND (? IS NULL OR ac.curso=?) AND (? IS NULL OR ac.periodo=?)''',
        (prof['id'], m, j, curso, curso, periodo, periodo)).fetchone()[0] if aids else 0
    pendientes = max(0, total_actividades * total_estudiantes - calificadas)
    students = _dashboard_student_grades(conn, slug, prof['id'], m, j, curso, periodo) if total_estudiantes else []
    finals = [s['nota_final'] for s in students if s['nota_final'] is not None]
    cfg = config_get(slug)
    escala_max = float(cfg.get('escala_max', 5.0))
    nota_min_aprobar = float(cfg.get('nota_minima_aprobar', 3.0))
    if escala_max > 5.0:
        nota_min_aprobar = nota_min_aprobar / 2.0
    aprobados = sum(1 for f in finals if f >= nota_min_aprobar)
    reprobados = sum(1 for f in finals if f < nota_min_aprobar)
    nota_max = max(finals) if finals else None
    nota_min = min(finals) if finals else None
    dist = {'0-1': 0, '1-2': 0, '2-3': 0, '3-4': 0, '4-5': 0}
    all_vals = conn.execute(
        '''SELECT n.val FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
            WHERE ac.profesor_id=? AND ac.materia=? AND ac.jornada=?
            AND (? IS NULL OR ac.curso=?) AND (? IS NULL OR ac.periodo=?)''',
        (prof['id'], m, j, curso, curso, periodo, periodo)).fetchall()
    for r in all_vals:
        v = r['val']
        if v < 1:
            dist['0-1'] += 1
        elif v < 2:
            dist['1-2'] += 1
        elif v < 3:
            dist['2-3'] += 1
        elif v < 4:
            dist['3-4'] += 1
        else:
            dist['4-5'] += 1
    distribucion = [{'label': k, 'count': v} for k, v in dist.items()]
    _batch_aids = aids or []
    if _batch_aids:
        ph_b = ','.join('?' * len(_batch_aids))
        all_notas_periodos = conn.execute(
            f'''SELECT n.aid, n.val, ac.periodo FROM notas n
                JOIN actividades ac ON ac.id=n.actividad_id
                WHERE n.aid IN ({ph_b}) AND ac.profesor_id=? AND ac.materia=? AND ac.jornada=?''',
            (*_batch_aids, prof['id'], m, j)).fetchall()
        all_ev_periodos = conn.execute(
            f'''SELECT aid, evaluacion, periodo FROM evaluaciones
                WHERE aid IN ({ph_b}) AND profesor_id=? AND materia=? AND jornada=?''',
            (*_batch_aids, prof['id'], m, j)).fetchall()
    else:
        all_notas_periodos = []; all_ev_periodos = []
    notas_by_aid_c = {}
    for r in all_notas_periodos:
        notas_by_aid_c.setdefault(r['aid'], []).append(r['val'])
    ev_by_aid_c = {}
    for r in all_ev_periodos:
        ev_by_aid_c[r['aid']] = r['evaluacion']
    prom_curso = []
    for c in cursos_q:
        cur_finals = []
        for a in all_alumnos:
            if a['curso'] != c:
                continue
            v = notas_by_aid_c.get(a['id'], [])
            e = ev_by_aid_c.get(a['id'])
            ff = _promedio_ponderado(v, e, None)
            if ff is not None:
                cur_finals.append(ff)
        prom_curso.append({'curso': c, 'promedio': round(sum(cur_finals) / len(cur_finals), 2) if cur_finals else None, 'count': len(cur_finals)})
    prom_materia = [{'materia': m, 'promedio': round(sum(finals) / len(finals), 2) if finals else None, 'count': len(finals)}]
    notas_by_aid_p = {}
    for r in all_notas_periodos:
        notas_by_aid_p.setdefault((r['aid'], r['periodo']), []).append(r['val'])
    ev_by_aid_p = {}
    for r in all_ev_periodos:
        ev_by_aid_p[(r['aid'], r['periodo'])] = r['evaluacion']
    evol = []
    for p in range(1, 5):
        finals_p = []
        for a in all_alumnos:
            vals_p = notas_by_aid_p.get((a['id'], p), [])
            ev_p = ev_by_aid_p.get((a['id'], p))
            ff = _promedio_ponderado(vals_p, ev_p, None)
            if ff is not None:
                finals_p.append(ff)
        evol.append({'periodo': p, 'promedio': round(sum(finals_p) / len(finals_p), 2) if finals_p else None, 'count': len(finals_p)})
    acts = conn.execute(
        'SELECT id, nombre FROM actividades WHERE profesor_id=? AND materia=? AND jornada=? AND (? IS NULL OR curso=?) AND (? IS NULL OR periodo=?) ORDER BY orden',
        (prof['id'], m, j, curso, curso, periodo, periodo)).fetchall()
    rend_acts = []
    if acts:
        act_ids = [a['id'] for a in acts]
        ph = ','.join('?' * len(act_ids))
        all_grades = conn.execute(
            f'SELECT actividad_id, val FROM notas WHERE actividad_id IN ({ph})', act_ids).fetchall()
        grades_by_act = {}
        for r in all_grades:
            grades_by_act.setdefault(r['actividad_id'], []).append(r['val'])
        for act in acts:
            vals = grades_by_act.get(act['id'], [])
            cnt = len(vals)
            prom = round(sum(vals) / cnt, 2) if cnt else None
            aprob = sum(1 for v in vals if v >= nota_min_aprobar) if vals else 0
            pct_aprob = round(aprob / cnt * 100, 1) if cnt else None
            rend_acts.append({'actividad': act['nombre'], 'promedio': prom, 'calificadas': cnt, 'porcentaje_aprobacion': pct_aprob})
    top_students = sorted(students, key=lambda s: s['nota_final'] or 0, reverse=True)[:10]
    top_cursos = sorted(prom_curso, key=lambda c: c['promedio'] or 0, reverse=True)
    threshold_bajo = 3.0
    bajo_est = [s for s in students if s['nota_final'] is not None and s['nota_final'] < threshold_bajo]
    bajo_cursos = [c for c in prom_curso if c['promedio'] is not None and c['promedio'] < 3.2]
    bajo_acts = [a for a in rend_acts if a['promedio'] is not None and a['promedio'] < 2.5]
    destacados = [s for s in students if s['nota_final'] is not None and s['nota_final'] > 4.5]
    stats = _estadisticas_desc(finals)
    return {
        'cards': {
            'promedio_curso': round(sum(finals) / len(finals), 2) if finals else None,
            'promedio_materia': round(sum(finals) / len(finals), 2) if finals else None,
            'total_estudiantes': total_estudiantes,
            'total_actividades': total_actividades,
            'actividades_calificadas': calificadas,
            'actividades_pendientes': pendientes,
            'aprobados': aprobados, 'reprobados': reprobados,
            'nota_max': nota_max, 'nota_min': nota_min,
        },
        'charts': {
            'distribucion': distribucion,
            'promedio_por_curso': prom_curso,
            'promedio_por_materia': prom_materia,
            'evolucion_periodos': evol,
            'rendimiento_actividades': rend_acts,
        },
        'rankings': {
            'top_estudiantes': [{'nombre': s['nombre'], 'promedio': s['nota_final']} for s in top_students],
            'top_cursos': top_cursos,
        },
        'alerts': {
            'estudiantes_bajo': [{'nombre': s['nombre'], 'promedio': s['nota_final'], 'curso': s['curso']} for s in bajo_est],
            'cursos_bajo': bajo_cursos,
            'actividades_bajo': bajo_acts,
            'destacados': [{'nombre': s['nombre'], 'promedio': s['nota_final'], 'curso': s['curso']} for s in destacados],
        },
        'estadisticas': stats,
    }


def _dashboard_rector_data(conn, slug, rector):
    total_estudiantes = conn.execute('SELECT COUNT(*) FROM alumnos WHERE activo=1').fetchone()[0]
    total_profesores = conn.execute('SELECT COUNT(*) FROM profesores WHERE activo=1').fetchone()[0]
    total_cursos = conn.execute('SELECT COUNT(DISTINCT curso) FROM alumnos WHERE activo=1').fetchone()[0]
    total_materias = conn.execute('SELECT COUNT(DISTINCT materia) FROM asignaciones_materia').fetchone()[0]
    total_actividades = conn.execute('SELECT COUNT(*) FROM actividades').fetchone()[0]
    solicitudes_pend = conn.execute("SELECT COUNT(*) FROM solicitudes_modificacion WHERE estado='pendiente' AND slug=?", (slug,)).fetchone()[0]
    periodos = conn.execute('SELECT periodo, estado FROM periodos_estado').fetchall()
    periodos_abiertos = sum(1 for p in periodos if p['estado'] == 'abierto')
    periodos_cerrados = sum(1 for p in periodos if p['estado'] == 'cerrado')
    cfg = config_get(slug)
    escala_max = float(cfg.get('escala_max', 5.0))
    nota_min_aprobar = float(cfg.get('nota_minima_aprobar', 3.0))
    if escala_max > 5.0:
        nota_min_aprobar /= 2.0
    alumnos = conn.execute(
        'SELECT id, nombre, curso, jornada FROM alumnos WHERE activo=1 ORDER BY id'
    ).fetchall()
    alumno_map = {a['id']: a for a in alumnos}
    profes = conn.execute('SELECT id, nombre FROM profesores WHERE activo=1').fetchall()
    asignaciones = conn.execute(
        'SELECT profesor_id, materia, jornada FROM asignaciones_materia'
    ).fetchall()
    prof_subjects = {}
    for a in asignaciones:
        prof_subjects.setdefault(a['profesor_id'], []).append((a['materia'], a['jornada']))
    notas_all = conn.execute('''
        SELECT n.aid, n.val, ac.materia, ac.jornada, ac.profesor_id, ac.curso
        FROM notas n
        JOIN actividades ac ON ac.id = n.actividad_id
    ''').fetchall()
    ev_all = conn.execute(
        'SELECT aid, materia, jornada, evaluacion, autoevaluacion FROM evaluaciones'
    ).fetchall()
    notas_idx = {}
    for r in notas_all:
        key = (r['aid'], r['materia'], r['jornada'])
        notas_idx.setdefault(key, []).append(r['val'])
    ev_idx = {}
    for r in ev_all:
        key = (r['aid'], r['materia'], r['jornada'])
        ev_idx[key] = r
    student_subject_grades = {}
    all_keys = set(notas_idx) | set(ev_idx)
    for aid, materia, jornada in all_keys:
        if aid not in alumno_map:
            continue
        vals = notas_idx.get((aid, materia, jornada), [])
        ev = ev_idx.get((aid, materia, jornada))
        ev_v = ev['evaluacion'] if ev and ev['evaluacion'] is not None else None
        au_v = ev['autoevaluacion'] if ev and ev['autoevaluacion'] is not None else None
        final = _promedio_ponderado(vals, ev_v, au_v)
        key = (aid, materia, jornada)
        student_subject_grades[key] = final
    student_avgs = {}
    for (aid, materia, jornada), final in student_subject_grades.items():
        if final is not None:
            student_avgs.setdefault(aid, []).append(final)
    student_overall = {}
    for aid, vals in student_avgs.items():
        student_overall[aid] = round(sum(vals) / len(vals), 2)
    all_finals = list(student_overall.values())
    prof_avgs = {}
    for p in profes:
        p_vals = []
        for (aid, materia, jornada), final in student_subject_grades.items():
            if final is not None:
                is_teacher_subject = any(
                    m == materia and j == jornada
                    for m, j in prof_subjects.get(p['id'], [])
                )
                if is_teacher_subject:
                    p_vals.append(final)
        if p_vals:
            prof_avgs[p['nombre']] = round(sum(p_vals) / len(p_vals), 2)
    prom_institucional = round(sum(all_finals) / len(all_finals), 2) if all_finals else None
    curso_avgs = {}
    for a in alumnos:
        avg = student_overall.get(a['id'])
        if avg is not None:
            curso_avgs.setdefault(a['curso'], []).append(avg)
    curso_avgs = {k: round(sum(v) / len(v), 2) for k, v in curso_avgs.items()}
    mejor_curso = max(curso_avgs, key=curso_avgs.get) if curso_avgs else None
    peor_curso = min(curso_avgs, key=curso_avgs.get) if curso_avgs else None
    subj_vals = {}
    for (aid, materia, jornada), final in student_subject_grades.items():
        if final is not None:
            subj_vals.setdefault(materia, []).append(final)
    subj_avgs = {k: round(sum(v) / len(v), 2) for k, v in subj_vals.items()}
    mejor_materia = max(subj_avgs, key=subj_avgs.get) if subj_avgs else None
    peor_materia = min(subj_avgs, key=subj_avgs.get) if subj_avgs else None
    dist = {'0-1': 0, '1-2': 0, '2-3': 0, '3-4': 0, '4-5': 0}
    for row in conn.execute('SELECT val FROM notas').fetchall():
        v = row['val']
        if v < 1:
            dist['0-1'] += 1
        elif v < 2:
            dist['1-2'] += 1
        elif v < 3:
            dist['2-3'] += 1
        elif v < 4:
            dist['3-4'] += 1
        else:
            dist['4-5'] += 1
    top_docentes = sorted(prof_avgs.items(), key=lambda x: x[1], reverse=True)[:10]
    bajo_list = []
    for aid, avg in sorted(student_overall.items(), key=lambda x: x[1]):
        if avg < nota_min_aprobar:
            a = alumno_map.get(aid)
            if a:
                bajo_list.append({'nombre': a['nombre'], 'promedio': avg, 'curso': a['curso']})
                if len(bajo_list) >= 20:
                    break
    stats = _estadisticas_desc(all_finals)
    return {
        'cards': {
            'total_estudiantes': total_estudiantes, 'total_profesores': total_profesores,
            'total_cursos': total_cursos, 'total_materias': total_materias,
            'total_actividades': total_actividades,
            'promedio_institucional': prom_institucional,
            'mejor_curso': mejor_curso, 'peor_curso': peor_curso,
            'mejor_materia': mejor_materia, 'peor_materia': peor_materia,
            'solicitudes_pendientes': solicitudes_pend,
            'periodos_abiertos': periodos_abiertos, 'periodos_cerrados': periodos_cerrados,
        },
        'charts': {
            'distribucion': [{'label': k, 'count': v} for k, v in dist.items()],
            'promedio_por_curso': [{'curso': k, 'promedio': v} for k, v in sorted(curso_avgs.items(), key=lambda x: x[1], reverse=True)],
            'promedio_por_materia': [{'materia': k, 'promedio': v} for k, v in sorted(subj_avgs.items(), key=lambda x: x[1], reverse=True)],
            'rendimiento_actividades': [],
        },
        'rankings': {
            'top_estudiantes': [],
            'top_cursos': [{'curso': k, 'promedio': v} for k, v in sorted(curso_avgs.items(), key=lambda x: x[1], reverse=True)[:10]],
            'top_docentes': [{'nombre': n, 'promedio': v} for n, v in top_docentes],
        },
        'alerts': {
            'estudiantes_bajo': bajo_list,
            'cursos_bajo': [{'curso': k, 'promedio': v} for k, v in sorted(curso_avgs.items(), key=lambda x: x[1]) if v < 3.2],
            'destacados': [],
        },
        'estadisticas': stats,
    }
