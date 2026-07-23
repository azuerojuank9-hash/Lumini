import logging
from datetime import datetime, timedelta
from io import BytesIO

from flask import Blueprint, Response, jsonify, redirect, render_template, request, url_for

from app.services.attendance_service import (
    COLORES_ASISTENCIA,
    ESTADOS_ASISTENCIA,
    build_asistencia_calendario,
    compute_asistencia_alertas,
    compute_asistencia_stats,
)
from app.utils.security import validar_csrf

logger = logging.getLogger(__name__)

attendance_bp = Blueprint('attendance', __name__)


def _fa():
    import flask_app
    return flask_app


@attendance_bp.route('/<slug>/asistencia', methods=['GET'])
def asistencia(slug):
    f = _fa()
    f.require_colegio(slug)
    prof = f.get_profesor(slug)
    if not prof:
        return redirect(url_for('auth.login', slug=slug))
    jornada, materia = f.get_sesion_jornada_materia(slug)
    if not jornada or not materia:
        return redirect(url_for('teacher.seleccionar_jornada', slug=slug))
    colegio = f.get_colegio(slug)
    mis_cursos = f.get_cursos_profesor(slug, prof['id'], materia, jornada)
    curso_sel = request.args.get('curso', mis_cursos[0] if mis_cursos else None)
    fecha_sel = request.args.get('fecha', datetime.today().strftime('%Y-%m-%d'))
    try:
        fecha_dt = datetime.strptime(fecha_sel, '%Y-%m-%d') if fecha_sel else datetime.today()
    except ValueError:
        fecha_sel = datetime.today().strftime('%Y-%m-%d')
        fecha_dt = datetime.today()
    fecha_sel_dia_anterior = (fecha_dt - timedelta(days=1)).strftime('%Y-%m-%d')
    fecha_sel_dia_siguiente = (fecha_dt + timedelta(days=1)).strftime('%Y-%m-%d')
    hoy_fecha = datetime.today().strftime('%Y-%m-%d')
    hoy_hora = datetime.today().strftime('%H:%M')
    if not curso_sel:
        return render_template('asistencia.html', profesor=prof, slug=slug, colegio=colegio,
                               materia=materia, jornada=jornada, mis_cursos=mis_cursos,
                               curso_sel=None, estudiantes=[], fecha_sel=fecha_sel,
                               fecha_sel_dia_anterior=fecha_sel_dia_anterior,
                               fecha_sel_dia_siguiente=fecha_sel_dia_siguiente,
                               hoy_fecha=hoy_fecha, hoy_hora=hoy_hora,
                               estados_asistencia=ESTADOS_ASISTENCIA,
                               colores_asistencia=COLORES_ASISTENCIA,
                               materias_jornadas=f.get_materias_profesor(slug, prof['id']))
    conn = f.conectar(slug)
    try:
        from app.repositories.attendance_repository import get_asistencia_for_date, get_students_by_curso
        alumnos = get_students_by_curso(conn, curso_sel, jornada)
        asis_rows = []
        if alumnos:
            aid_tuple = tuple(a['id'] for a in alumnos)
            asis_rows = get_asistencia_for_date(conn, fecha_sel, list(aid_tuple))
        asis_map = {r['aid']: {'estado': r['estado'], 'observacion': r['observacion'] or '', 'hora': r['hora'] or ''} for r in asis_rows}
        datos = []
        for a in alumnos:
            info = asis_map.get(a['id'], {})
            datos.append({
                'id': a['id'], 'nombre': a['nombre'],
                'num_curso': a['num_curso'],
                'asistencia': info.get('estado', ''),
                'observacion': info.get('observacion', ''),
                'hora': info.get('hora', ''),
            })
        stats = compute_asistencia_stats(conn, curso=curso_sel, jornada=jornada)
    finally:
        conn.close()
    return render_template('asistencia.html', profesor=prof, slug=slug, colegio=colegio,
                           materia=materia, jornada=jornada, mis_cursos=mis_cursos,
                           curso_sel=curso_sel, estudiantes=datos, fecha_sel=fecha_sel,
                           fecha_sel_dia_anterior=fecha_sel_dia_anterior,
                           fecha_sel_dia_siguiente=fecha_sel_dia_siguiente,
                           hoy_fecha=hoy_fecha, hoy_hora=hoy_hora,
                           stats=stats,
                           estados_asistencia=ESTADOS_ASISTENCIA,
                           colores_asistencia=COLORES_ASISTENCIA,
                           materias_jornadas=f.get_materias_profesor(slug, prof['id']))


@attendance_bp.route('/<slug>/marcar_asistencia', methods=['POST'])
def marcar_asistencia(slug):
    f = _fa()
    f.require_colegio(slug)
    prof = f.get_profesor(slug)
    if not prof:
        return ('', 403)
    if not validar_csrf():
        return ('Error CSRF', 403)
    aid = request.form.get('aid', type=int)
    estado = request.form.get('estado')
    fecha = request.form.get('fecha', '')
    observacion = request.form.get('observacion', '').strip()
    hora = request.form.get('hora', '')
    if aid is None or not estado:
        return ('', 400)
    if estado not in ESTADOS_ASISTENCIA:
        return ('', 400)
    if fecha:
        try:
            datetime.strptime(fecha, '%Y-%m-%d')
        except ValueError:
            return ('', 400)
    jornada, materia = f.get_sesion_jornada_materia(slug)
    conn = f.conectar(slug)
    cursos_prof = f.get_cursos_profesor(slug, prof['id'], materia, jornada)
    if not cursos_prof:
        conn.close()
        return ('', 403)
    from app.repositories.attendance_repository import upsert_asistencia, verify_student_in_cursos
    if not verify_student_in_cursos(conn, aid, cursos_prof, jornada):
        conn.close()
        return ('', 403)
    upsert_asistencia(conn, aid, fecha if fecha else None, estado, observacion, hora, 'profesor', prof['id'])
    conn.commit()
    f.audit_log(slug, prof['id'], 'asistencia_editada', 'asistencia', aid,
                None, {'estado': estado, 'observacion': observacion, 'hora': hora})
    conn.close()
    return jsonify({'status': 'ok'})


@attendance_bp.route('/<slug>/asistencia_data')
def asistencia_data(slug):
    f = _fa()
    f.require_colegio(slug)
    prof = f.get_profesor(slug)
    if not prof:
        return jsonify({'error': 'No autorizado'}), 403
    jornada, materia = f.get_sesion_jornada_materia(slug)
    if not jornada or not materia:
        return jsonify({'error': 'Sin jornada/materia'}), 400
    conn = f.conectar(slug)
    try:
        curso = request.args.get('curso', '')
        if not curso:
            conn.close()
            return jsonify({'error': 'Curso requerido'}), 400
        stats = compute_asistencia_stats(conn, curso=curso, jornada=jornada)
        alertas = compute_asistencia_alertas(conn, slug, curso, jornada)
        calendario = build_asistencia_calendario(conn, curso, jornada)
    finally:
        conn.close()
    return jsonify({
        'stats': stats,
        'alertas': alertas,
        'calendario': {k: dict(v) for k, v in calendario.items()},
        'estados': dict(ESTADOS_ASISTENCIA),
        'colores': COLORES_ASISTENCIA,
    })


@attendance_bp.route('/<slug>/asistencia_reporte_excel')
def asistencia_reporte_excel(slug):
    f = _fa()
    f.require_colegio(slug)
    prof = f.get_profesor(slug)
    if not prof:
        return ('', 403)
    jornada, materia = f.get_sesion_jornada_materia(slug)
    if not jornada or not materia:
        return ('', 400)
    conn = f.conectar(slug)
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        wb = Workbook()
        ws = wb.active
        ws.title = 'Asistencia'
        hd_font = Font(bold=True, color='FFFFFF', size=11)
        hd_fill = PatternFill('solid', fgColor='1E293B')
        thin = Side(style='thin', color='334155')
        border = Border(top=thin, left=thin, right=thin, bottom=thin)
        curso = request.args.get('curso', '')
        if not curso:
            conn.close()
            return ('Curso requerido', 400)
        from app.repositories.attendance_repository import get_asistencia_full, get_students_by_curso
        alumnos = get_students_by_curso(conn, curso, jornada)
        if not alumnos:
            conn.close()
            return ('Sin estudiantes', 404)
        aids = [a['id'] for a in alumnos]
        asis_rows = get_asistencia_full(conn, aids)
        fechas = sorted(set(r['fecha'] for r in asis_rows))
        header = ['#', 'Estudiante'] + fechas
        ws.append(header)
        for c in range(1, len(header) + 1):
            cell = ws.cell(row=1, column=c)
            cell.font = hd_font
            cell.fill = hd_fill
            cell.border = border
            cell.alignment = Alignment(horizontal='center', vertical='center')
        asis_map = {}
        for r in asis_rows:
            asis_map.setdefault(r['aid'], {})[r['fecha']] = {'estado': r['estado'], 'obs': r['observacion'] or ''}
        for i, a in enumerate(alumnos, start=2):
            ws.append([a['num_curso'], a['nombre']] + [asis_map.get(a['id'], {}).get(f, {}).get('estado', '') for f in fechas])
            for c in range(1, len(header) + 1):
                ws.cell(row=i, column=c).border = border
        ws.column_dimensions['A'].width = 5
        ws.column_dimensions['B'].width = 30
        for ci in range(3, len(header) + 1):
            ws.column_dimensions[chr(64 + ci) if ci <= 26 else 'A'].width = 7
    finally:
        conn.close()
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return Response(output.getvalue(),
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f'attachment; filename=asistencia_{slug}_{curso}.xlsx'})
