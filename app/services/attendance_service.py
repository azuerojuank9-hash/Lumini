import logging
from collections import defaultdict
from datetime import datetime as _dt

logger = logging.getLogger(__name__)

ESTADOS_ASISTENCIA = {'P': 'Presente', 'A': 'Ausente', 'T': 'Tardanza', 'E': 'Excusa', 'X': 'Permiso', 'S': 'Salida anticipada'}
COLORES_ASISTENCIA = {'P': 'green', 'A': 'red', 'T': 'yellow', 'E': 'blue', 'X': 'purple', 'S': 'orange'}


def compute_asistencia_stats(conn, curso=None, jornada=None, aid=None):
    from app.repositories.attendance_repository import get_students_by_curso, get_asistencia_stats, get_student_ids_by_curso
    where_curso = curso
    where_jornada = jornada
    if aid:
        rows = [{'id': aid}]
    else:
        rows = get_student_ids_by_curso(conn, where_curso, where_jornada) if (where_curso and where_jornada) else []
        if not rows:
            stats = {k: 0 for k in ESTADOS_ASISTENCIA}
            stats['total'] = 0
            stats['porcentaje_asistencia'] = 0
            stats['porcentaje_inasistencia'] = 0
            stats['porcentaje_tardanzas'] = 0
            return stats
    aids = [r['id'] for r in rows]
    stats = {k: 0 for k in ESTADOS_ASISTENCIA}
    stats['total'] = 0
    if aids:
        asis_rows = get_asistencia_stats(conn, aids)
        total = 0
        for ar in asis_rows:
            stats[ar['estado']] = ar['c']
            total += ar['c']
        stats['total'] = total
    stats['porcentaje_asistencia'] = round(stats['P'] / total * 100, 1) if total else 0
    stats['porcentaje_inasistencia'] = round((stats['A'] + stats['E'] + stats['X'] + stats['S']) / total * 100, 1) if total else 0
    stats['porcentaje_tardanzas'] = round(stats['T'] / total * 100, 1) if total else 0
    return stats


def compute_asistencia_alertas(conn, slug, curso, jornada):
    from app.repositories.attendance_repository import (
        get_students_by_curso, get_asistencia_abs_consec,
        get_asistencia_tardanzas, get_asistencia_all_stats
    )
    alertas = []
    alumnos = get_students_by_curso(conn, curso, jornada)
    if not alumnos:
        return alertas
    aids = [a['id'] for a in alumnos]

    abs_consec = get_asistencia_abs_consec(conn, aids)
    por_alumno = defaultdict(list)
    for r in abs_consec:
        por_alumno[r['aid']].append(r['fecha'])
    for aid, fechas in por_alumno.items():
        fechas = sorted(set(fechas))
        streak = 1
        max_streak = 1
        for i in range(1, len(fechas)):
            diff = (_dt.strptime(fechas[i], '%Y-%m-%d') - _dt.strptime(fechas[i-1], '%Y-%m-%d')).days
            if diff == 1:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 1
        if max_streak >= 3:
            alumno = next((a for a in alumnos if a['id'] == aid), None)
            if alumno:
                alertas.append({'aid': aid, 'nombre': alumno['nombre'], 'tipo': 'ausencias_consecutivas', 'detalle': f'{max_streak} ausencias consecutivas', 'severidad': 'alta'})

    tardanzas = get_asistencia_tardanzas(conn, aids)
    tard_map = {r['aid']: r['c'] for r in tardanzas}
    for aid, c in tard_map.items():
        if c > 5:
            alumno = next((a for a in alumnos if a['id'] == aid), None)
            if alumno:
                alertas.append({'aid': aid, 'nombre': alumno['nombre'], 'tipo': 'tardanzas_excesivas', 'detalle': f'{c} tardanzas registradas', 'severidad': 'media' if c <= 10 else 'alta'})

    asis_stats = get_asistencia_all_stats(conn, aids)
    stats_por_aid = {}
    for r in asis_stats:
        stats_por_aid.setdefault(r['aid'], {})[r['estado']] = r['c']
    for alumno in alumnos:
        s = stats_por_aid.get(alumno['id'], {})
        total_s = sum(s.values())
        if total_s > 0:
            pct = round((s.get('P', 0) + s.get('X', 0)) / total_s * 100)
            if pct < 80:
                alertas.append({'aid': alumno['id'], 'nombre': alumno['nombre'], 'tipo': 'baja_asistencia', 'detalle': f'{pct}% asistencia', 'severidad': 'alta'})

    return alertas


def build_asistencia_calendario(conn, curso, jornada):
    from app.repositories.attendance_repository import get_student_ids_by_curso, get_asistencia_all_dates
    alumnos = get_student_ids_by_curso(conn, curso, jornada)
    aids = tuple(a['id'] for a in alumnos)
    calendario = defaultdict(lambda: defaultdict(int))
    if aids:
        rows = get_asistencia_all_dates(conn, list(aids))
        for r in rows:
            calendario[r['fecha']][r['estado']] += 1
    return calendario
