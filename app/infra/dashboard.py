import logging
from collections import Counter, defaultdict
from datetime import date

from app.infra.database import config_get
from app.infra.grades import _promedio_ponderado

logger = logging.getLogger(__name__)

SEV_ORDEN = {'critica': 0, 'atencion': 1, 'informacion': 2, 'positiva': 3}

MESES_ABR = ['ene', 'feb', 'mar', 'abr', 'may', 'jun',
             'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

DIAS_SEMANA_ABR = ['Lun', 'Mar', 'Mi\u00e9', 'Jue', 'Vie', 'S\u00e1b', 'Dom']


def _estado_estudiante(promedio):
    """Estado visual coherente con FASE 4.1 (tabla de notas / drawer del
    estudiante): <2.8 atencion (rojo), 2.8–3.5 medio (amarillo), >3.5 bueno."""
    if promedio is None:
        return None
    if promedio < 2.8:
        return 'atencion'
    if promedio <= 3.5:
        return 'medio'
    return 'bueno'


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


def _asistencia_alertas_centro(conn, all_alumnos):
    """Alertas de asistencia agregadas (cursos del docente) con los MISMOS
    criterios de LUMINI (attendance._asistencia_alertas) pero en consultas
    agrupadas (sin N+1): ausencias consecutivas >=3, tardanzas >5,
    asistencia (P+X) < 80%."""
    alertas = []
    if not all_alumnos:
        return alertas
    aids = [a['id'] for a in all_alumnos]
    alumnos = list(all_alumnos)
    ph = ','.join('?' * len(aids))

    abs_consec = conn.execute(
        f"SELECT aid, fecha FROM asistencia WHERE aid IN ({ph}) AND estado='A' AND fecha >= date('now','-30 days') ORDER BY aid, fecha",
        aids).fetchall()
    por_alumno = defaultdict(list)
    for r in abs_consec:
        por_alumno[r['aid']].append(r['fecha'])
    for aid, fechas in por_alumno.items():
        fechas = sorted(set(fechas))
        streak = 1
        max_streak = 1
        for i in range(1, len(fechas)):
            diff = (date.fromisoformat(fechas[i]) - date.fromisoformat(fechas[i - 1])).days
            if diff == 1:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 1
        if max_streak >= 3:
            alumno = next((a for a in alumnos if a['id'] == aid), None)
            if alumno:
                alertas.append({'aid': aid, 'nombre': alumno['nombre'], 'curso': alumno['curso'],
                                'tipo': 'ausencias_consecutivas', 'detalle': f'{max_streak} ausencias consecutivas',
                                'severidad': 'alta'})

    tardanzas = conn.execute(
        f'SELECT aid, COUNT(*) as c FROM asistencia WHERE aid IN ({ph}) AND estado="T" GROUP BY aid',
        aids).fetchall()
    for r in tardanzas:
        if r['c'] > 5:
            alumno = next((a for a in alumnos if a['id'] == r['aid']), None)
            if alumno:
                alertas.append({'aid': r['aid'], 'nombre': alumno['nombre'], 'curso': alumno['curso'],
                                'tipo': 'tardanzas_excesivas', 'detalle': f'{r["c"]} tardanzas registradas',
                                'severidad': 'media' if r['c'] <= 10 else 'alta'})

    asis_stats = conn.execute(
        f'SELECT aid, estado, COUNT(*) as c FROM asistencia WHERE aid IN ({ph}) GROUP BY aid, estado',
        aids).fetchall()
    stats_por_aid = {}
    for r in asis_stats:
        stats_por_aid.setdefault(r['aid'], {})[r['estado']] = r['c']
    for alumno in alumnos:
        s = stats_por_aid.get(alumno['id'], {})
        total = sum(s.values())
        if total > 0:
            pct = round((s.get('P', 0) + s.get('X', 0)) / total * 100)
            if pct < 80:
                alertas.append({'aid': alumno['id'], 'nombre': alumno['nombre'], 'curso': alumno['curso'],
                                'tipo': 'baja_asistencia', 'detalle': f'{pct}% asistencia', 'severidad': 'alta'})
    return alertas


def _asistencia_inteligente(conn, all_alumnos, cursos_q, jornada, materia):
    """Asistencia inteligente del docente (ETAPA F). Reutiliza EXACTAMENTE los
    criterios de LUMINI (app/infra/attendance.py y ETAPA C): asistencia
    (P+X) < 80%, ausencias consecutivas >= 3, tardanzas > 5. Sin umbrales
    nuevos. Consultas agrupadas (sin N+1)."""
    out = {'cursos': [], 'ultimo_registro': None, 'ultimo_registro_fmt': None,
           'faltan_hoy': [], 'ausencias_bajas': []}
    if not all_alumnos or not cursos_q:
        return out
    aids = [a['id'] for a in all_alumnos]
    ph = ','.join('?' * len(aids))
    curso_by_aid = {a['id']: a['curso'] for a in all_alumnos}

    # (1) Conteos por alumno y estado (cubre pct y tardanzas).
    regs = conn.execute(
        f'SELECT aid, estado, COUNT(*) AS c FROM asistencia WHERE aid IN ({ph}) GROUP BY aid, estado',
        aids).fetchall()
    stats_por_aid = {}
    for r in regs:
        stats_por_aid.setdefault(r['aid'], {})[r['estado']] = r['c']

    # (2) Ausencias de los últimos 30 días (rachas consecutivas >= 3).
    abs30 = conn.execute(
        f"SELECT aid, fecha FROM asistencia WHERE aid IN ({ph}) AND estado='A' "
        "AND fecha >= date('now','-30 days') ORDER BY aid, fecha", aids).fetchall()
    por_alumno = defaultdict(list)
    for r in abs30:
        por_alumno[r['aid']].append(r['fecha'])
    consec = set()
    for aid, fechas in por_alumno.items():
        fechas = sorted(set(fechas))
        streak = 1
        max_streak = 1
        for i in range(1, len(fechas)):
            diff = (date.fromisoformat(fechas[i]) - date.fromisoformat(fechas[i - 1])).days
            if diff == 1:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 1
        if max_streak >= 3:
            consec.add(aid)

    # (3) Última fecha con registro real (nunca fabricada).
    ult = conn.execute(
        f'SELECT MAX(fecha) AS m FROM asistencia WHERE aid IN ({ph})', aids).fetchone()
    ult_fecha = (ult['m'] or '')[:10] if ult else ''
    if ult_fecha:
        try:
            dd = date.fromisoformat(ult_fecha)
            out['ultimo_registro'] = ult_fecha
            out['ultimo_registro_fmt'] = f'{dd.day} {MESES_ABR[dd.month - 1]}'
        except ValueError:
            pass

    # (4) Registros de hoy (misma convención que la ruta de asistencia).
    hoy = date.today()
    hoy_aids = {r['aid'] for r in conn.execute(
        'SELECT DISTINCT aid FROM asistencia WHERE aid IN ({}) AND fecha=?'.format(ph),
        (*aids, hoy.isoformat())).fetchall()}

    # (5) Cursos con clase HOY según el horario real (materia del docente).
    clases_hoy = set()
    if jornada:
        ph_c = ','.join('?' for _ in cursos_q)
        rows_ho = conn.execute(
            'SELECT DISTINCT curso FROM horarios_curso WHERE curso IN ({}) '
            'AND jornada=? AND dia=? AND materia=?'.format(ph_c),
            (*cursos_q, jornada, DIAS_SEMANA_ABR[hoy.weekday()], materia)).fetchall()
        clases_hoy = {r['curso'] for r in rows_ho}

    # Agregación por curso.
    curso_est = {}
    for r in regs:
        curso = curso_by_aid.get(r['aid'])
        if not curso:
            continue
        d = curso_est.setdefault(curso, {})
        d[r['estado']] = d.get(r['estado'], 0) + r['c']

    # Estudiantes que disparan algún criterio LUMINI.
    baja = []
    for a in all_alumnos:
        s = stats_por_aid.get(a['id'], {})
        total = sum(s.values())
        if total == 0:
            continue
        pct = round((s.get('P', 0) + s.get('X', 0)) / total * 100)
        tard = s.get('T', 0)
        tipos = []
        if pct < 80:
            tipos.append('baja_asistencia')
        if a['id'] in consec:
            tipos.append('ausencias_consecutivas')
        if tard > 5:
            tipos.append('tardanzas_excesivas')
        if tipos:
            baja.append({'aid': a['id'], 'nombre': a['nombre'], 'curso': a['curso'],
                         'pct': pct, 'tardanzas': tard, 'tipos': tipos})

    # Estado por curso: atencion > pendiente > bien.
    cursos_out = []
    for c in cursos_q:
        est = curso_est.get(c, {})
        total = sum(est.values())
        pct = round((est.get('P', 0) + est.get('X', 0)) / total * 100, 1) if total else None
        tiene_hoy = any(a['curso'] == c and a['id'] in hoy_aids for a in all_alumnos)
        faltante = c in clases_hoy and not tiene_hoy
        if any(x['curso'] == c for x in baja):
            estado = 'atencion'
        elif faltante:
            estado = 'pendiente'
        else:
            estado = 'bien'
        cursos_out.append({
            'curso': c, 'estado': estado, 'porcentaje': pct,
            'P': est.get('P', 0), 'A': est.get('A', 0), 'T': est.get('T', 0),
            'total': total, 'clase_hoy': c in clases_hoy, 'faltante_hoy': faltante,
        })
    out['cursos'] = cursos_out
    out['faltan_hoy'] = [{'curso': c['curso']} for c in cursos_out if c['faltante_hoy']]
    out['ausencias_bajas'] = [
        {'nombre': x['nombre'], 'curso': x['curso'], 'pct': x['pct'],
         'razon': ', '.join(x['tipos'])}
        for x in sorted(baja, key=lambda x: x['pct'])[:6]]
    return out


def _construir_alerta(severidad, tipo, titulo, descripcion, accion=None, dismiss_key=None):
    return {
        'severidad': severidad,
        'tipo': tipo,
        'titulo': titulo,
        'descripcion': descripcion,
        'accion': accion,
        'dismiss_key': dismiss_key,
    }


def _plural_estudiantes(n):
    return '1 estudiante' if n == 1 else f'{n} estudiantes'


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
    if cursos_q:
        placeholders = ','.join('?' for _ in cursos_q)
        all_alumnos = conn.execute(
            f'SELECT id, nombre, curso FROM alumnos WHERE curso IN ({placeholders}) AND jornada=? AND activo=1 ORDER BY nombre',
            (*cursos_q, j)).fetchall()
    else:
        all_alumnos = []
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
    max_periodo = max((r['periodo'] for r in all_ev_periodos), default=4)
    for p in range(1, max_periodo + 1):
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
    # ── Resumen del docente (aditivo; las claves existentes no cambian) ──
    resumen = {
        'notas_pendientes_por_curso': [],
        'notas_pendientes_total': 0,
        'notas_esperadas_total': 0,
        'notas_calificadas_total': 0,
        'proximas_actividades': [],
        'tendencia': None,
        'mejor_rendimiento': None,
        'menor_rendimiento': None,
        'estudiantes_que_mejoraron': [],
        'estudiantes_que_bajaron': [],
    }
    try:
        # Notas pendientes por curso (reales): grilla esperada - registradas.
        pend_por_curso = []
        pend_total = 0
        exp_total = 0
        reg_total = 0
        if cursos_q:
            ph_c = ','.join('?' for _ in cursos_q)
            rows_grid = conn.execute(
                f'''SELECT ac.curso, COUNT(DISTINCT al.id) AS est, COUNT(DISTINCT ac.id) AS acts
                    FROM actividades ac
                    JOIN alumnos al ON al.curso=ac.curso AND al.jornada=? AND al.activo=1
                    WHERE ac.profesor_id=? AND ac.materia=? AND ac.jornada=?
                      AND ac.estado_act='publicada'
                      AND ac.curso IN ({ph_c}) AND (? IS NULL OR ac.periodo=?)
                    GROUP BY ac.curso''',
                (j, prof['id'], m, j, *cursos_q, periodo, periodo)).fetchall()
            rows_reg = conn.execute(
                f'''SELECT ac.curso, COUNT(*) AS c
                    FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
                    WHERE ac.profesor_id=? AND ac.materia=? AND ac.jornada=?
                      AND ac.estado_act='publicada'
                      AND ac.curso IN ({ph_c}) AND (? IS NULL OR ac.periodo=?)
                    GROUP BY ac.curso''',
                (prof['id'], m, j, *cursos_q, periodo, periodo)).fetchall()
            reg_by_curso = {r['curso']: r['c'] for r in rows_reg}
            for r in rows_grid:
                est = r['est']
                acts = r['acts']
                exp = est * acts
                reg = reg_by_curso.get(r['curso'], 0)
                pend = max(0, exp - reg)
                pend_por_curso.append({
                    'curso': r['curso'], 'estudiantes': est, 'actividades': acts,
                    'esperadas': exp, 'calificadas': reg, 'pendientes': pend,
                })
                pend_total += pend
                exp_total += exp
                reg_total += reg
            pend_por_curso.sort(key=lambda x: x['pendientes'], reverse=True)
        resumen['notas_pendientes_por_curso'] = pend_por_curso
        resumen['notas_pendientes_total'] = pend_total
        resumen['notas_esperadas_total'] = exp_total
        resumen['notas_calificadas_total'] = reg_total

        # Próximas actividades: solo fecha_limite futura (nunca vencidas).
        # Se filtra por curso si el docente filtró; NO por período, para que
        # una actividad futura de otro período no desaparezca del resumen.
        rows_prox = conn.execute(
            '''SELECT id, nombre, curso, materia, periodo, estado_act, fecha_limite
               FROM actividades
               WHERE profesor_id=? AND materia=? AND jornada=?
                 AND fecha_limite IS NOT NULL AND fecha_limite >= date('now')
                 AND (? IS NULL OR curso=?)
               ORDER BY fecha_limite, orden LIMIT 8''',
            (prof['id'], m, j, curso, curso)).fetchall()
        resumen['proximas_actividades'] = [
            {'id': r['id'], 'nombre': r['nombre'], 'curso': r['curso'],
             'materia': r['materia'] or '', 'periodo': r['periodo'],
             'estado_act': r['estado_act'] or 'publicada',
             'fecha_limite': r['fecha_limite'][:10]}
            for r in rows_prox]

        # Tendencia del curso reutilizando evolucion_periodos (sin fórmula nueva).
        tendencia = None
        evol_real = [p for p in evol if p['promedio'] is not None]
        if len(evol_real) >= 2:
            primero = evol_real[0]['promedio']
            ultimo = evol_real[-1]['promedio']
            delta = round(ultimo - primero, 2)
            if delta > 0.01:
                direccion = 'sube'
            elif delta < -0.01:
                direccion = 'baja'
            else:
                direccion = 'estable'
            tendencia = {'direccion': direccion, 'delta': delta, 'periodos': len(evol_real)}
        resumen['tendencia'] = tendencia

        # Mejor / menor rendimiento (cálculos académicos existentes).
        mejor = None
        menor = None
        con_final = [s for s in students if s['nota_final'] is not None]
        if con_final:
            mejor_obj = max(con_final, key=lambda s: s['nota_final'])
            menor_obj = min(con_final, key=lambda s: s['nota_final'])
            mejor = {'nombre': mejor_obj['nombre'], 'curso': mejor_obj['curso'],
                     'promedio': mejor_obj['nota_final']}
            menor = {'nombre': menor_obj['nombre'], 'curso': menor_obj['curso'],
                     'promedio': menor_obj['nota_final']}
        resumen['mejor_rendimiento'] = mejor
        resumen['menor_rendimiento'] = menor

        # Estudiantes que mejoraron / bajaron usando períodos reales en memoria.
        # Se compara el último período con nota contra el anterior; solo con
        # información suficiente (>=2 períodos) y cambio >= 0.5.
        finals_aid_p = {}
        if aids:
            for aid in aids:
                serie = []
                for p in range(1, max_periodo + 1):
                    vals_p = notas_by_aid_p.get((aid, p), [])
                    ev_p = ev_by_aid_p.get((aid, p))
                    ff = _promedio_ponderado(vals_p, ev_p, None)
                    if ff is not None:
                        serie.append((p, ff))
                finals_aid_p[aid] = serie
        mejoraron = []
        bajaron = []
        for a in all_alumnos:
            serie = finals_aid_p.get(a['id'], [])
            if len(serie) < 2:
                continue
            prev = serie[-2][1]
            cur = serie[-1][1]
            d = round(cur - prev, 2)
            if d >= 0.5:
                mejoraron.append({'nombre': a['nombre'], 'curso': a['curso'],
                                  'desde': prev, 'hasta': cur, 'delta': d})
            elif d <= -0.5:
                bajaron.append({'nombre': a['nombre'], 'curso': a['curso'],
                                'desde': prev, 'hasta': cur, 'delta': d})
        mejoraron.sort(key=lambda x: x['delta'], reverse=True)
        bajaron.sort(key=lambda x: x['delta'])
        resumen['estudiantes_que_mejoraron'] = mejoraron[:10]
        resumen['estudiantes_que_bajaron'] = bajaron[:10]

        # ── Rendimiento inteligente (ETAPA E): sección "Rendimiento de
        #    estudiantes". Reutiliza cálculos ya en memoria (sin queries
        #    nuevas): mejoraron/bajaron, con_final, notas_by_aid_p/ev_by_aid_p.
        rend = {}
        if con_final:
            top = sorted(con_final, key=lambda s: s['nota_final'], reverse=True)[:5]
            bottom = sorted(con_final, key=lambda s: s['nota_final'])[:5]
            rend['mejores'] = [{'nombre': s['nombre'], 'curso': s['curso'],
                                'promedio': s['nota_final'],
                                'estado': _estado_estudiante(s['nota_final'])} for s in top]
            rend['menores'] = [{'nombre': s['nombre'], 'curso': s['curso'],
                                'promedio': s['nota_final'],
                                'estado': _estado_estudiante(s['nota_final'])} for s in bottom]
        else:
            rend['mejores'] = []
            rend['menores'] = []

        def _map_delta(e):
            return {'nombre': e['nombre'], 'curso': e['curso'],
                    'promedio': e['hasta'], 'delta': e['delta'],
                    'estado': _estado_estudiante(e['hasta'])}
        rend['mejoran'] = [_map_delta(e) for e in mejoraron[:5]]
        rend['atencion'] = [_map_delta(e) for e in bajaron[:5]]

        # Tendencia por curso (en memoria): promedio por período por curso.
        serie_curso = {}
        for p in range(1, max_periodo + 1):
            by_curso = defaultdict(list)
            for a in all_alumnos:
                vals_p = notas_by_aid_p.get((a['id'], p), [])
                ev_p = ev_by_aid_p.get((a['id'], p))
                ff = _promedio_ponderado(vals_p, ev_p, None)
                if ff is not None:
                    by_curso[a['curso']].append(ff)
            for c, vals in by_curso.items():
                serie_curso.setdefault(c, []).append((p, round(sum(vals) / len(vals), 2)))
        cursos_rend = []
        for c in cursos_q:
            serie = serie_curso.get(c, [])
            if not serie:
                continue
            promedio = serie[-1][1]
            delta = None
            if len(serie) >= 2:
                delta = round(serie[-1][1] - serie[-2][1], 2)
            cursos_rend.append({'curso': c, 'promedio': promedio, 'delta': delta,
                                'periodos': len(serie)})
        cursos_rend.sort(key=lambda x: x['promedio'], reverse=True)
        rend['cursos'] = cursos_rend
        resumen['rendimiento_estudiantes'] = rend

        # Asistencia inteligente (ETAPA F): semáforo por curso, último
        # registro, cursos pendientes de hoy y estudiantes con asistencia baja.
        resumen['asistencia_inteligente'] = _asistencia_inteligente(
            conn, all_alumnos, cursos_q, j, m)
    except Exception:
        logger.warning('dashboard: no se pudo construir el resumen del docente', exc_info=True)

    # ── Centro de Alertas (aditivo; solo datos reales ya disponibles) ──
    criticas = []
    atencion = []
    informacion = []
    positivas = []
    try:
        # Rendimiento: estudiantes con promedio < 3.0 por curso (umbral existente).
        bajo_por_curso = {}
        for s in students:
            if s['nota_final'] is not None and s['nota_final'] < 3.0:
                bajo_por_curso.setdefault(s['curso'], []).append(s)
        for curso_c, lst in bajo_por_curso.items():
            criticas.append(_construir_alerta(
                'critica', 'rendimiento',
                _plural_estudiantes(len(lst)) + ' con bajo rendimiento',
                f'Promedio menor a 3.0 · {curso_c}',
                {'label': 'Ver estudiantes', 'url': f'/{slug}/?curso={curso_c}'},
                f'alerta:rendimiento:bajo:{curso_c}:{len(lst)}'))

        # Rendimiento: estudiantes que bajaron significativamente (>=0.5 real).
        bajaron = resumen.get('estudiantes_que_bajaron', [])
        if bajaron:
            nombres = ', '.join(s['nombre'] for s in bajaron[:3]) + ('...' if len(bajaron) > 3 else '')
            atencion.append(_construir_alerta(
                'atencion', 'rendimiento',
                _plural_estudiantes(len(bajaron)) + ' bajaron su rendimiento',
                f'Comparando el \u00faltimo per\u00edodo con el anterior · {nombres}',
                {'label': 'Ver rendimiento', 'url': f'/{slug}/'},
                f'alerta:rendimiento:bajaron:{len(bajaron)}'))

        # Rendimiento: cursos con promedio bajo (<3.2, umbral existente).
        # Se omite si el curso ya tiene alerta crítica de estudiantes.
        cursos_con_critica = set(bajo_por_curso.keys())
        for c in prom_curso:
            if c['promedio'] is not None and c['promedio'] < 3.2 and c['curso'] not in cursos_con_critica:
                atencion.append(_construir_alerta(
                    'atencion', 'rendimiento',
                    f'Curso {c["curso"]} con promedio bajo',
                    f'Promedio: {c["promedio"]}',
                    {'label': 'Ver rendimiento', 'url': f'/{slug}/?curso={c["curso"]}'},
                    f'alerta:rendimiento:curso:{c["curso"]}:{c["promedio"]}'))

        # Rendimiento: destacados (>4.5).
        destacados_ok = resumen and resumen.get('mejor_rendimiento')
        if destacados:
            informacion.append(_construir_alerta(
                'informacion', 'rendimiento',
                _plural_estudiantes(len(destacados)) + ' destacados',
                'Promedio mayor a 4.5',
                {'label': 'Ver rendimiento', 'url': f'/{slug}/'},
                f'alerta:rendimiento:destacados:{len(destacados)}'))

        # Notas: pendientes / sin calificar / al día por curso (conteos reales).
        for c in resumen.get('notas_pendientes_por_curso', []):
            if c.get('actividades', 0) == 0:
                continue
            pend = c.get('pendientes', 0)
            if pend > 0 and c.get('calificadas', 0) == 0:
                criticas.append(_construir_alerta(
                    'critica', 'notas',
                    f'Curso {c["curso"]} sin calificar',
                    f'{c["esperadas"]} notas por registrar',
                    {'label': 'Registrar notas', 'url': f'/{slug}/?curso={c["curso"]}'},
                    f'alerta:notas:sin_calificar:{c["curso"]}:{c["esperadas"]}'))
            elif pend > 0:
                atencion.append(_construir_alerta(
                    'atencion', 'notas',
                    f'{pend} notas pendientes en {c["curso"]}',
                    f'{c["calificadas"]} de {c["esperadas"]} registradas',
                    {'label': 'Registrar notas', 'url': f'/{slug}/?curso={c["curso"]}'},
                    f'alerta:notas:pendientes:{c["curso"]}:{pend}'))
            elif c.get('esperadas', 0) > 0:
                positivas.append(_construir_alerta(
                    'positiva', 'notas',
                    f'Curso {c["curso"]} al d\u00eda',
                    'Todas las notas registradas',
                    {'label': 'Ver notas', 'url': f'/{slug}/?curso={c["curso"]}'},
                    f'alerta:notas:completo:{c["curso"]}:{c["esperadas"]}'))

        # Actividades: hoy / mañana / próximas (fecha_limite real, nunca vencidas).
        hoy = date.today()
        prox_info = 0
        for a in resumen.get('proximas_actividades', []):
            fl = (a.get('fecha_limite') or '')[:10]
            try:
                diff = (date.fromisoformat(fl) - hoy).days if fl else None
            except ValueError:
                diff = None
            if diff is None:
                continue
            url = f'/{slug}/?curso={a.get("curso", "")}'
            dk = f'alerta:actividad:{a.get("id")}:{fl}'
            if diff == 0:
                criticas.append(_construir_alerta(
                    'critica', 'actividad',
                    f'Actividad para hoy: {a.get("nombre", "")}',
                    f'{a.get("curso", "")} · vence hoy',
                    {'label': 'Ver actividad', 'url': url}, dk))
            elif diff == 1:
                atencion.append(_construir_alerta(
                    'atencion', 'actividad',
                    f'Actividad para ma\u00f1ana: {a.get("nombre", "")}',
                    f'{a.get("curso", "")} · vence ma\u00f1ana',
                    {'label': 'Ver actividad', 'url': url}, dk))
            elif 2 <= diff <= 7 and prox_info < 3:
                prox_info += 1
                informacion.append(_construir_alerta(
                    'informacion', 'actividad',
                    f'Actividad pr\u00f3xima: {a.get("nombre", "")}',
                    f'{a.get("curso", "")} · vence el {fl}',
                    {'label': 'Ver actividad', 'url': url}, dk))

        # Asistencia: mismos criterios LUMINI, agregados por curso (3 consultas).
        asis_alertas = _asistencia_alertas_centro(conn, all_alumnos)
        caps = {'ausencias_consecutivas': 0, 'tardanzas_excesivas': 0, 'baja_asistencia': 0}
        for aa in asis_alertas:
            if caps.get(aa['tipo'], 0) >= 5:
                continue
            caps[aa['tipo']] = caps.get(aa['tipo'], 0) + 1
            url = f'/{slug}/asistencia?curso={aa["curso"]}'
            dk = f"alerta:asistencia:{aa['tipo']}:{aa['aid']}"
            sev = 'critica' if aa['severidad'] == 'alta' else 'atencion'
            titulo = f"{aa['nombre']}: {aa['detalle']}"
            desc = f'Curso {aa["curso"]}'
            (criticas if sev == 'critica' else atencion).append(_construir_alerta(
                sev, 'asistencia', titulo, desc,
                {'label': 'Ver asistencia', 'url': url}, dk))

        # Rendimiento: estudiantes que mejoraron (>=0.5 real) → positiva.
        mejoraron = resumen.get('estudiantes_que_mejoraron', [])
        if mejoraron:
            positivas.append(_construir_alerta(
                'positiva', 'rendimiento',
                _plural_estudiantes(len(mejoraron)) + ' mejoraron su rendimiento',
                'Comparando el \u00faltimo per\u00edodo con el anterior',
                {'label': 'Ver rendimiento', 'url': f'/{slug}/'},
                f'alerta:rendimiento:mejoraron:{len(mejoraron)}'))

        def _orden(a):
            return SEV_ORDEN.get(a['severidad'], 99)

        alerts_centro = sorted(criticas + atencion + informacion + positivas, key=_orden)
        alerts_centro = alerts_centro[:25]
        conteos = {
            'criticas': sum(1 for a in alerts_centro if a['severidad'] == 'critica'),
            'atencion': sum(1 for a in alerts_centro if a['severidad'] == 'atencion'),
            'informacion': sum(1 for a in alerts_centro if a['severidad'] == 'informacion'),
            'positivas': sum(1 for a in alerts_centro if a['severidad'] == 'positiva'),
            'total': len(alerts_centro),
        }
    except Exception:
        logger.warning('dashboard: no se pudo construir el centro de alertas', exc_info=True)
        alerts_centro = []
        conteos = {'criticas': 0, 'atencion': 0, 'informacion': 0, 'positivas': 0, 'total': 0}
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
        'resumen': resumen,
        'alerts_centro': alerts_centro,
        'alerts_conteos': conteos,
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
