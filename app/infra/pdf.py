from io import BytesIO
from app.infra.database import conectar
from app.infra.grades import _promedio_ponderado


def generar_pdf_alumno(alumno, slug, colegio, curso, jornada, periodo, conn):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
    except ImportError:
        raise ImportError(
            'reportlab no está instalado. '
            'PDF no disponible. Instálelo con: pip install reportlab'
        )

    lista_materias = [r['materia'] for r in conn.execute(
        'SELECT DISTINCT materia FROM actividades WHERE curso=? AND jornada=? AND COALESCE(periodo,1)=? ORDER BY materia',
        (curso, jornada, periodo)
    ).fetchall()]

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    try:
        pri_color = colors.HexColor(colegio['primary_color']) if colegio and colegio['primary_color'] else colors.HexColor('#6c63ff')
    except (KeyError, AttributeError, TypeError):
        pri_color = colors.HexColor('#6c63ff')
    try:
        sec_color = colors.HexColor(colegio['secondary_color']) if colegio and colegio['secondary_color'] else colors.HexColor('#3498db')
    except (KeyError, AttributeError, TypeError):
        sec_color = colors.HexColor('#3498db')
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('t', fontSize=16, fontName='Helvetica-Bold',
                                  textColor=pri_color, spaceAfter=4)
    sub_style    = ParagraphStyle('s', fontSize=10, fontName='Helvetica',
                                  textColor=colors.grey, spaceAfter=10)
    mat_style    = ParagraphStyle('m', fontSize=11, fontName='Helvetica-Bold',
                                  textColor=pri_color, spaceBefore=10, spaceAfter=4)
    story = []
    story.append(Paragraph('LUMINI', titulo_style))
    story.append(Paragraph(
        f'Boletín — {colegio["nombre"] if colegio else slug} · {jornada} · Periodo {periodo}', sub_style))
    story.append(Paragraph(f'Estudiante: {alumno["nombre"]}   |   Curso: {curso}', styles['Normal']))
    story.append(Spacer(1, 0.4*cm))

    todos_finales = []
    ph = ','.join('?' * len(lista_materias))
    notas_all = conn.execute(
        f'''SELECT ac.materia, n.val FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
            WHERE n.aid=? AND ac.materia IN ({ph}) AND ac.curso=? AND ac.jornada=?
            AND COALESCE(ac.periodo,1)=?''',
        (alumno['id'],) + tuple(lista_materias) + (curso, jornada, periodo)
    ).fetchall()
    ev_all = conn.execute(
        f'''SELECT materia, evaluacion, autoevaluacion FROM evaluaciones
            WHERE aid=? AND materia IN ({ph}) AND jornada=? AND COALESCE(periodo,1)=?''',
        (alumno['id'],) + tuple(lista_materias) + (jornada, periodo)
    ).fetchall()
    notas_por_mat = {}
    for r in notas_all:
        notas_por_mat.setdefault(r['materia'], []).append(r['val'])
    ev_por_mat = {}
    for r in ev_all:
        ev_por_mat[r['materia']] = r
    for mat in lista_materias:
        notas_vals = notas_por_mat.get(mat, [])
        ev = ev_por_mat.get(mat)
        eval_v   = ev['evaluacion']     if ev and ev['evaluacion']     is not None else None
        auto_v   = ev['autoevaluacion'] if ev and ev['autoevaluacion'] is not None else None
        final = _promedio_ponderado(notas_vals, eval_v, auto_v)
        act_prom = round(sum(notas_vals) / len(notas_vals), 2) if notas_vals else None

        story.append(Paragraph(mat, mat_style))
        data = [['Actividades', 'Evaluación', 'Autoevaluación', 'Nota Final'],
                [str(act_prom) if act_prom is not None else '—',
                 str(eval_v)   if eval_v   is not None else '—',
                 str(auto_v)   if auto_v   is not None else '—',
                 str(final)    if final    is not None else '—']]
        t = Table(data, colWidths=[4*cm, 3.5*cm, 3.5*cm, 3*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), pri_color),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, -1), 9),
            ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
            ('GRID',       (0, 0), (-1, -1), 0.3, colors.HexColor('#cccccc')),
        ]))
        story.append(t)
        if final is not None:
            todos_finales.append(final)

    prom_general = round(sum(todos_finales) / len(todos_finales), 2) if todos_finales else None
    story.append(Spacer(1, 0.5*cm))
    estado = 'Pendiente' if prom_general is None else ('Aprobado' if prom_general >= 3.0 else 'Reprobado')
    bg_color = pri_color if prom_general is not None and prom_general >= 3.0 else colors.HexColor('#e74c3c') if prom_general is not None else colors.HexColor('#64748B')
    resumen = Table(
        [['PROMEDIO GENERAL', str(prom_general) if prom_general is not None else '—', 'ESTADO', estado]],
        colWidths=[5*cm, 3*cm, 3*cm, 3*cm]
    )
    resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg_color),
        ('TEXTCOLOR',  (0, 0), (-1, -1), colors.white),
        ('FONTNAME',   (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 11),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(resumen)
    story.append(Spacer(1, 1*cm))
    doc.build(story)
    buf.seek(0)
    return buf.read(), prom_general
