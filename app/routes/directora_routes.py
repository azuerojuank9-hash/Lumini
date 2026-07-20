from io import BytesIO
from datetime import date
from flask import render_template, request, redirect, url_for, jsonify, Response
from app.routes import directora_bp


def _fa():
    import sys
    if 'flask_app' in sys.modules:
        return sys.modules['flask_app']
    import flask_app
    return flask_app


@directora_bp.route('/<slug>/directora')
@directora_bp.route('/<slug>/directora/panel')
def directora_panel(slug):
    fa = _fa()
    fa.require_colegio(slug)
    directora = fa.get_directora(slug)
    if not directora:
        return redirect(url_for('auth.directora_login', slug=slug))
    colegio = fa.get_colegio(slug)
    curso = directora['curso']
    jornada = directora['jornada']
    periodo = request.args.get('periodo', 1, type=int)
    num_periodos = int(colegio['num_periodos']) if colegio and colegio['num_periodos'] else 4
    conn = fa.conectar(slug)
    alumnos = conn.execute(
        'SELECT * FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre COLLATE NOCASE',
        (curso, jornada)).fetchall()
    lista_materias = [r['materia'] for r in conn.execute(
        'SELECT DISTINCT materia FROM actividades WHERE curso=? AND jornada=? AND COALESCE(periodo,1)=? ORDER BY materia',
        (curso, jornada, periodo)).fetchall()]
    profs_raw = conn.execute(
        '''SELECT DISTINCT am.materia, p.nombre,
           (SELECT COUNT(*) FROM actividades a
            WHERE a.profesor_id=p.id AND a.curso=? AND a.jornada=?
            AND COALESCE(a.periodo,1)=?) as cnt
           FROM profesores p
           JOIN asignaciones_curso ac ON ac.profesor_id=p.id
           JOIN asignaciones_materia am ON am.profesor_id=p.id AND am.jornada=ac.jornada AND am.materia=ac.materia
           WHERE ac.curso=? AND ac.jornada=? AND p.activo=1''',
        (curso, jornada, periodo, curso, jornada)).fetchall()
    materias_enviadas = set()
    profesores = []
    for p in profs_raw:
        enviado = p['cnt'] > 0
        if enviado:
            materias_enviadas.add(p['materia'])
        profesores.append({'materia': p['materia'], 'nombre': p['nombre'],
                           'enviado': enviado, 'fecha_envio': None})
    aid_alumno = {a['id'] for a in alumnos}
    notas_all = conn.execute(
        '''SELECT n.aid, ac.materia, n.val FROM notas n
           JOIN actividades ac ON ac.id=n.actividad_id
           WHERE ac.curso=? AND ac.jornada=? AND COALESCE(ac.periodo,1)=?
           ORDER BY n.aid, ac.materia''',
        (curso, jornada, periodo)).fetchall()
    notas_by = {}
    for r in notas_all:
        notas_by.setdefault((r['aid'], r['materia']), []).append(r['val'])
    if aid_alumno:
        evals_all = conn.execute(
            '''SELECT aid, materia, evaluacion, autoevaluacion FROM evaluaciones
               WHERE aid IN ({}) AND COALESCE(periodo,1)=?'''.format(
                   ','.join('?' * len(aid_alumno))),
            (*aid_alumno, periodo)).fetchall()
    else:
        evals_all = []
    evals_by = {}
    for r in evals_all:
        evals_by[(r['aid'], r['materia'])] = r
    tabla = []
    for a in alumnos:
        fila = {'id': a['id'], 'nombre': a['nombre'],
                'email': a['email_acudiente'] or '', 'materias': {}, 'promedio': None}
        todos_finales = []
        for mat in lista_materias:
            notas_vals = notas_by.get((a['id'], mat), [])
            ev = evals_by.get((a['id'], mat))
            eval_v = ev['evaluacion'] if ev and ev['evaluacion'] is not None else None
            auto_v = ev['autoevaluacion'] if ev and ev['autoevaluacion'] is not None else None
            final = fa._promedio_ponderado(notas_vals, eval_v, auto_v)
            act_prom = round(sum(notas_vals) / len(notas_vals), 2) if notas_vals else None
            fila['materias'][mat] = {'act': act_prom, 'eval': eval_v, 'auto': auto_v, 'final': final}
            if final is not None:
                todos_finales.append(final)
        fila['promedio'] = round(sum(todos_finales) / len(todos_finales), 2) if todos_finales else None
        tabla.append(fila)
    actividad_reciente = conn.execute(
        '''SELECT accion, tabla, creado
           FROM audit_log ORDER BY creado DESC LIMIT 6''').fetchall()
    actividad_reciente = [dict(r) for r in actividad_reciente]
    notif_count = conn.execute(
        'SELECT COUNT(*) as c FROM notificaciones WHERE usuario_tipo=? AND usuario_id=? AND leida=0',
        ('directora', directora['id'])).fetchone()['c']
    aprobados = sum(1 for f in tabla if f['promedio'] is not None and f['promedio'] >= 3.0)
    reprobados = sum(1 for f in tabla if f['promedio'] is not None and f['promedio'] < 3.0)
    sin_notas = sum(1 for f in tabla if f['promedio'] is None)
    conn.close()
    return render_template('directora_panel.html',
                           slug=slug, colegio=colegio, directora=directora,
                           curso=curso, jornada=jornada, periodo=periodo,
                           num_periodos=num_periodos,
                           lista_materias=lista_materias,
                           materias_enviadas=materias_enviadas,
                           profesores=profesores, tabla=tabla,
                           actividad_reciente=actividad_reciente,
                           notif_count=notif_count,
                           aprobados=aprobados, reprobados=reprobados,
                           sin_notas=sin_notas)


@directora_bp.route('/<slug>/directora/boletin_pdf')
def directora_boletin_pdf(slug):
    fa = _fa()
    fa.require_colegio(slug)
    directora = fa.get_directora(slug)
    if not directora:
        return redirect(url_for('auth.directora_login', slug=slug))
    colegio = fa.get_colegio(slug)
    curso = directora['curso']
    jornada = directora['jornada']
    periodo = request.args.get('periodo', 1, type=int)
    aid_solo = request.args.get('aid', type=int)
    conn = fa.conectar(slug)
    if aid_solo:
        alumnos = conn.execute(
            'SELECT * FROM alumnos WHERE id=? AND curso=?', (aid_solo, curso)).fetchall()
    else:
        alumnos = conn.execute(
            'SELECT * FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre COLLATE NOCASE',
            (curso, jornada)).fetchall()
    all_pdfs = []
    for alumno in alumnos:
        try:
            pdf_bytes, _ = fa.generar_pdf_alumno(alumno, slug, colegio, curso, jornada, periodo, conn)
        except ImportError:
            return render_template('error.html',
                                   codigo=501,
                                   mensaje='La generación de PDF requiere la librería <strong>reportlab</strong>. '
                                           'Consulte al administrador del sistema para instalarla.')
        all_pdfs.append(pdf_bytes)
    conn.close()
    if not all_pdfs:
        return ('Sin alumnos', 404)
    if len(all_pdfs) == 1:
        return Response(all_pdfs[0], mimetype='application/pdf',
                        headers={'Content-Disposition':
                                 f'attachment;filename=boletin_{curso}_{jornada}_P{periodo}.pdf'})
    try:
        from pypdf import PdfWriter, PdfReader
        writer = PdfWriter()
        for pdf_bytes in all_pdfs:
            reader = PdfReader(BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)
        out = BytesIO()
        writer.write(out)
        out.seek(0)
        return Response(out, mimetype='application/pdf',
                        headers={'Content-Disposition':
                                 f'attachment;filename=boletin_{curso}_{jornada}_P{periodo}.pdf'})
    except ImportError:
        return Response(all_pdfs[0], mimetype='application/pdf',
                        headers={'Content-Disposition':
                                 f'attachment;filename=boletin_{curso}_{jornada}_P{periodo}.pdf'})


@directora_bp.route('/<slug>/directora/enviar_correos', methods=['POST'])
def directora_enviar_correos(slug):
    fa = _fa()
    fa.require_colegio(slug)
    directora = fa.get_directora(slug)
    if not directora:
        return jsonify({'ok': False, 'mensaje': 'No autorizado'})
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'mensaje': 'Error CSRF'})
    import html as _html
    if not fa.SENDGRID_API_KEY:
        return jsonify({'ok': False, 'mensaje': 'Envío de correos no configurado (falta SENDGRID_API_KEY).'})
    colegio = fa.get_colegio(slug)
    curso = directora['curso']
    jornada = directora['jornada']
    periodo = int(request.form.get('periodo', 1))
    aid_solo = request.form.get('aid', type=int)
    conn = fa.conectar(slug)
    if aid_solo:
        alumnos = conn.execute(
            'SELECT * FROM alumnos WHERE id=? AND curso=?', (aid_solo, curso)).fetchall()
    else:
        alumnos = conn.execute(
            'SELECT * FROM alumnos WHERE curso=? AND jornada=? AND activo=1 ORDER BY nombre COLLATE NOCASE',
            (curso, jornada)).fetchall()
    enviados = fallidos = sin_correo = 0
    for alumno in alumnos:
        email_dest = alumno['email_acudiente'] if alumno['email_acudiente'] else None
        if not email_dest:
            sin_correo += 1
            continue
        try:
            pdf_bytes, prom_general = fa.generar_pdf_alumno(
                alumno, slug, colegio, curso, jornada, periodo, conn)
        except Exception as e:
            fa.logger.error(f'Error generando PDF para {alumno["nombre"]}: {e}')
            fallidos += 1
            continue
        asunto = f'Boletín de Notas — {alumno["nombre"]} · Periodo {periodo}'
        try:
            pri_hex = colegio['primary_color'] if colegio and colegio['primary_color'] else '#6c63ff'
        except (KeyError, AttributeError, TypeError):
            pri_hex = '#6c63ff'
        cuerpo = f'''<div style="font-family:sans-serif;max-width:500px;margin:0 auto;">
            <h2 style="color:{pri_hex};">LUMINI — Boletín de Notas</h2>
            <p>Estimado acudiente,</p>
            <p>Adjunto encontrará el boletín de notas de <strong>{_html.escape(str(alumno['nombre']))}</strong>
               correspondiente al <strong>Periodo {periodo}</strong>.</p>
            <p><strong>Promedio general: {prom_general}</strong></p>
            <p style="color:#888;font-size:12px;">
               {_html.escape(str(colegio['nombre'] if colegio else slug))} · {curso} · {jornada}</p>
        </div>'''
        adj_nombre = f'boletin_{alumno["nombre"].replace(" ", "_")}_P{periodo}.pdf'
        if fa.enviar_correo(email_dest, asunto, cuerpo, pdf_bytes, adj_nombre, 'application/pdf'):
            enviados += 1
            fa.logger.info(f'Boletín enviado a {email_dest} para {alumno["nombre"]}')
        else:
            fallidos += 1
    conn.close()
    partes = []
    if enviados:
        partes.append(f'✅ {enviados} enviado(s)')
    if fallidos:
        partes.append(f'❌ {fallidos} fallido(s)')
    if sin_correo:
        partes.append(f'⚠️ {sin_correo} sin correo registrado')
    return jsonify({'ok': fallidos == 0, 'mensaje': ' · '.join(partes) or 'Sin destinatarios'})


@directora_bp.route('/<slug>/directora/guardar_email', methods=['POST'])
def directora_guardar_email(slug):
    fa = _fa()
    fa.require_colegio(slug)
    directora = fa.get_directora(slug)
    if not directora:
        return ('', 403)
    if not fa.validar_csrf():
        return ('Error CSRF', 403)
    aid = request.form.get('aid', type=int)
    email = request.form.get('email', '').strip()
    conn = fa.conectar(slug)
    conn.execute('UPDATE alumnos SET email_acudiente=? WHERE id=?', (email, aid))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@directora_bp.route('/<slug>/directora/crear_desde_panel', methods=['POST'])
def directora_crear_desde_panel(slug):
    fa = _fa()
    fa.require_colegio(slug)
    directora = fa.get_directora(slug)
    if not directora:
        return jsonify({'ok': False, 'mensaje': 'No autorizado'})
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'mensaje': 'Error CSRF'})
    fa.migrar_db(slug)
    nombre = request.form.get('nombre', '').strip()
    usuario = request.form.get('usuario', '').strip()
    pw = request.form.get('password', '').strip()
    curso = request.form.get('curso', '').strip()
    email = request.form.get('email', '').strip()
    jornada = directora['jornada']
    if not nombre or not usuario or not pw or not curso:
        return jsonify({'ok': False, 'mensaje': 'Completa todos los campos.'})
    if len(pw) < 6:
        return jsonify({'ok': False, 'mensaje': 'Mínimo 6 caracteres.'})
    conn = fa.conectar(slug)
    if conn.execute('SELECT 1 FROM directoras WHERE usuario=?', (usuario,)).fetchone():
        conn.close()
        return jsonify({'ok': False, 'mensaje': 'Ese usuario ya existe.'})
    conn.execute(
        'INSERT INTO directoras (nombre,usuario,password,curso,jornada,email) VALUES (?,?,?,?,?,?)',
        (nombre, usuario, fa.hash_pw(pw), curso, jornada, email))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'mensaje': f'Cuenta creada para {nombre}.'})
