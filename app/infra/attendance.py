from collections import defaultdict
from datetime import datetime as _dt

ESTADOS_ASISTENCIA = {'P': 'Presente', 'A': 'Ausente', 'T': 'Tardanza', 'E': 'Excusa', 'X': 'Permiso', 'S': 'Salida anticipada'}
COLORES_ASISTENCIA = {'P': 'green', 'A': 'red', 'T': 'yellow', 'E': 'blue', 'X': 'purple', 'S': 'orange'}


def _asistencia_stats(conn, curso=None, jornada=None, aid=None):
    where = 'WHERE activo=1'
    params = []
    if curso:
        where += ' AND curso=?'; params.append(curso)
    if jornada:
        where += ' AND jornada=?'; params.append(jornada)
    if aid:
        where += ' AND id=?'; params.append(aid)
    stats = {k: 0 for k in ESTADOS_ASISTENCIA}
    stats['total'] = 0
    rows = conn.execute(
        f'SELECT a.id FROM alumnos a {where} ORDER BY a.id', params).fetchall()
    if not rows:
        stats['porcentaje_asistencia'] = 0
        stats['porcentaje_inasistencia'] = 0
        stats['porcentaje_tardanzas'] = 0
        return stats
    aids = [r['id'] for r in rows]
    placeholders = ','.join('?' * len(aids))
    asis_rows = conn.execute(
        f'SELECT estado, COUNT(*) as c FROM asistencia WHERE aid IN ({placeholders}) GROUP BY estado',
        aids).fetchall()
    total = 0
    for ar in asis_rows:
        stats[ar['estado']] = ar['c']
        total += ar['c']
    stats['total'] = total
    stats['porcentaje_asistencia'] = round(stats['P'] / total * 100, 1) if total else 0
    stats['porcentaje_inasistencia'] = round((stats['A'] + stats['E'] + stats['X'] + stats['S']) / total * 100, 1) if total else 0
    stats['porcentaje_tardanzas'] = round(stats['T'] / total * 100, 1) if total else 0
    return stats


def _asistencia_alertas(conn, slug, curso, jornada):
    alertas = []
    alumnos = conn.execute(
        'SELECT id, nombre, num_curso FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre COLLATE NOCASE',
        (curso, jornada)).fetchall()
    if not alumnos:
        return alertas
    aids = [a['id'] for a in alumnos]
    placeholders = ','.join('?' * len(aids))
    abs_consec = conn.execute(
        f'''SELECT aid, fecha FROM asistencia
            WHERE aid IN ({placeholders}) AND estado='A' AND fecha >= date('now','-30 days')
            ORDER BY aid, fecha''', aids).fetchall()
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
    tardanzas = conn.execute(
        f'SELECT aid, COUNT(*) as c FROM asistencia WHERE aid IN ({placeholders}) AND estado="T" GROUP BY aid',
        aids).fetchall()
    tard_map = {r['aid']: r['c'] for r in tardanzas}
    for aid, c in tard_map.items():
        if c > 5:
            alumno = next((a for a in alumnos if a['id'] == aid), None)
            if alumno:
                alertas.append({'aid': aid, 'nombre': alumno['nombre'], 'tipo': 'tardanzas_excesivas', 'detalle': f'{c} tardanzas registradas', 'severidad': 'media' if c <= 10 else 'alta'})
    asis_stats = conn.execute(
        f'SELECT aid, estado, COUNT(*) as c FROM asistencia WHERE aid IN ({placeholders}) GROUP BY aid, estado',
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
                alertas.append({'aid': alumno['id'], 'nombre': alumno['nombre'], 'tipo': 'baja_asistencia', 'detalle': f'{pct}% asistencia', 'severidad': 'alta'})
    return alertas
