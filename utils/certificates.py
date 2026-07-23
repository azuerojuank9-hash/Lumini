"""
Professional Certificate PDF generation.

Generates high-quality PDF certificates:
- Constancia de estudio
- Certificado de estudio (final)
- Paz y salvo
- Reporte de notas
- Certificado de conducta
- Certificado de matrícula

Built on reportlab with institutional theming.
"""

from datetime import datetime
from io import BytesIO


def _init_styles():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CertTitle', parent=styles['Title'],
        fontSize=18, spaceAfter=6, textColor=colors.HexColor('#1a1a2e'),
        alignment=1,
    )
    normal_style = ParagraphStyle(
        'CertNormal', parent=styles['Normal'],
        fontSize=11, leading=16, spaceAfter=8,
    )
    return letter, cm, mm, colors, title_style, normal_style


def generar_constancia_estudio(alumno: dict, colegio: dict, firma_rector: str = '') -> BytesIO:
    """Generate 'Constancia de Estudio' PDF — proof of current enrollment."""
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    letter, cm, mm, colors, title_style, normal_style = _init_styles()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=2*cm, bottomMargin=2*cm)
    elements = []
    elements.append(Paragraph(f'<b>{colegio.get("nombre", "INSTITUCIÓN EDUCATIVA")}</b>', title_style))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph('CONSTANCIA DE ESTUDIO', title_style))
    elements.append(Spacer(1, 1*cm))

    text = (
        f'El (La) Rector(a) de la {colegio.get("nombre", "Institución Educativa")}, '
        f'en uso de sus atribuciones legales,</p><p><b>CERTIFICA</b></p><p>Que '
        f'<b>{alumno.get("nombre", "")}</b>, identificado(a) en el sistema con código '
        f'interno No. <b>{alumno.get("id", "")}</b>, es estudiante activo(a) de esta '
        f'institución, cursando <b>{alumno.get("curso", "")}</b> en la jornada '
        f'<b>{alumno.get("jornada", "")}</b>, durante el año lectivo {datetime.now().year}.'
    )
    elements.append(Paragraph(text, normal_style))
    elements.append(Spacer(1, 1*cm))
    elements.append(Paragraph(
        f'Se expide en {colegio.get("municipio", "la ciudad")}, a los {datetime.now().day} días '
        f'del mes de {datetime.now().strftime("%B")} de {datetime.now().year}.',
        normal_style
    ))
    elements.append(Spacer(1, 2*cm))

    if firma_rector:
        elements.append(Paragraph(f'________________________<br/>{firma_rector}<br/><b>Rector(a)</b>', normal_style))

    doc.build(elements)
    buf.seek(0)
    return buf


def generar_certificado_estudio(alumno: dict, colegio: dict, materias: list,
                                 promedio_general: float, firma_rector: str = '') -> BytesIO:
    """Generate 'Certificado de Estudio' PDF — final academic certificate with grades."""
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    letter, cm, mm, colors, title_style, normal_style = _init_styles()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=2*cm, bottomMargin=2*cm)
    elements = []
    elements.append(Paragraph(f'<b>{colegio.get("nombre", "INSTITUCIÓN EDUCATIVA")}</b>', title_style))
    elements.append(Spacer(1, 0.3*cm))
    elements.append(Paragraph('CERTIFICADO DE ESTUDIO', title_style))
    elements.append(Spacer(1, 0.8*cm))

    elements.append(Paragraph(
        f'El (La) suscrito(a) Rector(a) de la {colegio.get("nombre", "Institución Educativa")} '
        f'<b>CERTIFICA</b> que <b>{alumno.get("nombre", "")}</b> cursó y aprobó el grado '
        f'<b>{alumno.get("curso", "")}</b> durante el año lectivo {datetime.now().year}, '
        f'obteniendo los siguientes resultados:',
        normal_style
    ))
    elements.append(Spacer(1, 0.5*cm))

    table_data = [['Materia', 'Nota Final']]
    for m in materias:
        table_data.append([m.get('nombre', ''), f"{m.get('nota', 0):.1f}"])
    table_data.append(['<b>Promedio General</b>', f'<b>{promedio_general:.1f}</b>'])

    t = Table(table_data, colWidths=[12*cm, 4*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 1*cm))

    if firma_rector:
        elements.append(Paragraph(f'________________________<br/>{firma_rector}<br/><b>Rector(a)</b>', normal_style))

    doc.build(elements)
    buf.seek(0)
    return buf


def generar_paz_y_salvo(alumno: dict, colegio: dict, firma_rector: str = '') -> BytesIO:
    """Generate 'Paz y Salvo' PDF — clearance certificate."""
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    letter, cm, mm, colors, title_style, normal_style = _init_styles()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=2*cm, bottomMargin=2*cm)
    elements = []
    elements.append(Paragraph(f'<b>{colegio.get("nombre", "INSTITUCIÓN EDUCATIVA")}</b>', title_style))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph('PAZ Y SALVO', title_style))
    elements.append(Spacer(1, 1*cm))

    elements.append(Paragraph(
        f'La {colegio.get("nombre", "Institución Educativa")} hace constar que '
        f'<b>{alumno.get("nombre", "")}</b>, identificado(a) con código interno '
        f'<b>{alumno.get("id", "")}</b>, se encuentra a paz y salvo por todo concepto '
        f'con la institución al día de hoy {datetime.now().strftime("%d de %B de %Y")}.',
        normal_style
    ))
    elements.append(Spacer(1, 2*cm))

    if firma_rector:
        elements.append(Paragraph(f'________________________<br/>{firma_rector}<br/><b>Rector(a)</b>', normal_style))

    doc.build(elements)
    buf.seek(0)
    return buf


def generar_certificado_conducta(alumno: dict, colegio: dict, observaciones: list,
                                  firma_rector: str = '') -> BytesIO:
    """Generate 'Certificado de Conducta' PDF — behavior certificate."""
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    letter, cm, mm, colors, title_style, normal_style = _init_styles()

    positivas = sum(1 for o in observaciones if 'positivo' in o.get('texto', '').lower())
    negativas = len(observaciones) - positivas

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=2*cm, bottomMargin=2*cm)
    elements = []
    elements.append(Paragraph(f'<b>{colegio.get("nombre", "INSTITUCIÓN EDUCATIVA")}</b>', title_style))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph('CERTIFICADO DE CONDUCTA', title_style))
    elements.append(Spacer(1, 1*cm))

    conducta = 'EXCELENTE' if negativas == 0 else 'BUENA' if negativas <= 3 else 'ACEPTABLE'
    elements.append(Paragraph(
        f'La {colegio.get("nombre", "Institución Educativa")} certifica que '
        f'<b>{alumno.get("nombre", "")}</b>, estudiante de <b>{alumno.get("curso", "")}</b>, '
        f'ha demostrado una conducta <b>{conducta}</b> durante el período académico. '
        f'Registro de observaciones: {len(observaciones)} en total '
        f'({positivas} positivas, {negativas} negativas).',
        normal_style
    ))
    elements.append(Spacer(1, 2*cm))

    if firma_rector:
        elements.append(Paragraph(f'________________________<br/>{firma_rector}<br/><b>Rector(a)</b>', normal_style))

    doc.build(elements)
    buf.seek(0)
    return buf
