import logging

from flask import jsonify, redirect, render_template, request

from app.infra.mail import enviar_correo
from app.routes import admin_bp

logger = logging.getLogger(__name__)


def _fa():
    import flask_app as fa
    return fa


@admin_bp.route('/admin/codigos', methods=['GET', 'POST'])
@admin_bp.route('/admin/codigos/<slug>', methods=['GET', 'POST'])
def admin_codigos(slug=None):
    fa = _fa()
    if not fa.session.get('admin_auth'):
        return redirect(fa.url_for('auth.admin'))
    cm = fa.conectar_master()
    error = exito = None

    if request.method == 'POST':
        if not fa.validar_csrf():
            return 'Error de seguridad', 400
        accion = request.form.get('accion')
        if accion == 'actualizar_codigos':
            s = request.form.get('slug', '').strip()
            cod_prof = request.form.get('codigo_profesores', '').strip()
            cod_dir = request.form.get('codigo_directoras', '').strip()
            cod_rec = request.form.get('codigo_rectores', '').strip()
            cm.execute(
                'UPDATE colegios SET codigo_profesores=?, codigo_directoras=?, codigo_rectores=? WHERE slug=?',
                (cod_prof, cod_dir, cod_rec, s))
            cm.commit()
            exito = 'Códigos actualizados correctamente.'
            slug = s
        elif accion == 'generar_codigos':
            s = request.form.get('slug', '').strip()
            prefijo = request.form.get('prefijo', '').strip()
            if not prefijo:
                error = 'Elige un prefijo para los códigos.'
            else:
                import secrets as sec
                new_prof = f'{prefijo}_prof_{sec.token_hex(4)}'
                new_dir = f'{prefijo}_dir_{sec.token_hex(4)}'
                new_rec = f'{prefijo}_rec_{sec.token_hex(4)}'
                cm.execute(
                    'UPDATE colegios SET codigo_profesores=?, codigo_directoras=?, codigo_rectores=? WHERE slug=?',
                    (new_prof, new_dir, new_rec, s))
                cm.commit()
                exito = f'Códigos generados para {s}: Profesores={new_prof}, Directoras={new_dir}, Rectores={new_rec}'
                slug = s

    colegios = cm.execute('SELECT * FROM colegios ORDER BY nombre').fetchall()
    colegio_selected = None
    if slug:
        colegio_selected = cm.execute('SELECT * FROM colegios WHERE slug=?', (slug,)).fetchone()
    cm.close()
    return render_template('admin_codigos.html',
                           colegios=colegios, colegio=colegio_selected,
                           error=error, exito=exito)


@admin_bp.route('/admin/profesores/<slug>')
def admin_ver_profesores(slug):
    fa = _fa()
    if not fa.session.get('admin_auth'):
        return jsonify({'error': 'No autorizado'}), 403
    if not fa.get_colegio(slug):
        return jsonify({'error': 'Colegio no encontrado'}), 404
    fa.init_db(slug)
    conn = fa.conectar(slug)
    try:
        profs = conn.execute(
            'SELECT id, nombre, usuario, activo FROM profesores ORDER BY nombre').fetchall()
        resultado = []
        for p in profs:
            mats = conn.execute(
                'SELECT materia, jornada FROM asignaciones_materia WHERE profesor_id=? ORDER BY jornada, materia',
                (p['id'],)).fetchall()
            resultado.append({
                'nombre': p['nombre'], 'usuario': p['usuario'], 'activo': p['activo'],
                'materias': [{'materia': m['materia'], 'jornada': m['jornada']} for m in mats]
            })
        return jsonify({'profesores': resultado})
    finally:
        conn.close()


@admin_bp.route('/admin/correos')
def admin_correos():
    fa = _fa()
    if not fa.session.get('admin_auth'):
        return redirect(fa.url_for('auth.admin'))
    cm = fa.conectar_master()
    colegios = cm.execute('SELECT * FROM colegios ORDER BY nombre').fetchall()
    cm.close()
    return render_template('admin_correos.html', colegios=colegios)


@admin_bp.route('/admin/correos/<path:accion>', methods=['POST'])
@admin_bp.route('/admin/recordatorio_pago', methods=['POST'])
@admin_bp.route('/admin/enviar_correo', methods=['POST'])
def admin_correos_handler(accion=None):
    fa = _fa()
    if not fa.session.get('admin_auth'):
        return redirect(fa.url_for('auth.admin'))
    if not fa.validar_csrf():
        return 'Error de seguridad', 400

    if accion is None:
        if request.path.startswith('/admin/recordatorio_pago'):
            accion = 'recordatorio_pago'
        elif request.path.startswith('/admin/enviar_correo'):
            accion = 'enviar_correo'

    cm = fa.conectar_master()
    colegios = cm.execute('SELECT * FROM colegios ORDER BY nombre').fetchall()
    error = None
    exito = None

    try:
        if accion == 'enviar_anuncio':
            slugs = request.form.getlist('slugs')
            asunto = request.form.get('asunto', '').strip()
            mensaje = request.form.get('mensaje', '').strip()
            email_destino = request.form.get('email_destino', '').strip()
            if not slugs and not email_destino:
                error = 'Selecciona al menos un colegio o ingresa un correo destino.'
            elif not asunto or not mensaje:
                error = 'Asunto y mensaje son requeridos.'
            else:
                destinos = []
                if email_destino:
                    destinos.append(email_destino)
                for s in slugs:
                    row = cm.execute('SELECT email, nombre FROM colegios WHERE slug=?', (s,)).fetchone()
                    if row and row['email']:
                        destinos.append(row['email'])
                for d in destinos:
                    _enviar_email_admin(d, asunto, _plantilla_html(asunto, mensaje))
                exito = f'Anuncio enviado a {len(destinos)} destinatario(s).'

        elif accion == 'recordatorio_pago':
            slug = request.form.get('slug', '').strip()
            email = request.form.get('email', '').strip()
            row = cm.execute('SELECT nombre, vencimiento FROM colegios WHERE slug=?', (slug,)).fetchone()
            if not row:
                error = 'Colegio no encontrado.'
            elif not email:
                error = 'Correo destino requerido.'
            else:
                vence = row['vencimiento'] or 'próximamente'
                cuerpo = (
                    f'Hola,<br><br>'
                    f'El acceso de <b>{row["nombre"]}</b> vence el <b>{vence}</b>.<br><br>'
                    f'Para renovar su suscripción y mantener el acceso a Lumini, '
                    f'por favor realice el pago antes de la fecha indicada.<br><br>'
                    f'— Equipo Lumini'
                )
                _enviar_email_admin(email, 'Recordatorio de pago — Lumini', _plantilla_html(asunto='Recordatorio de pago', cuerpo=cuerpo, alerta=True))
                exito = f'Recordatorio enviado a {email}.'

        elif accion == 'recordatorio_masivo':
            slugs = request.form.getlist('slugs')
            email_fallback = request.form.get('email_fallback', '').strip()
            enviados = 0
            for s in slugs:
                row = cm.execute('SELECT email, nombre, vencimiento FROM colegios WHERE slug=?', (s,)).fetchone()
                dest = (row['email'] if row and row['email'] else email_fallback) if row else None
                if dest:
                    vence = row['vencimiento'] or 'próximamente'
                    cuerpo = (
                        f'Hola,<br><br>'
                        f'El acceso de <b>{row["nombre"]}</b> vence el <b>{vence}</b>.<br><br>'
                        f'Para renovar su suscripción y mantener el acceso a Lumini, '
                        f'por favor realice el pago antes de la fecha indicada.<br><br>'
                        f'— Equipo Lumini'
                    )
                    _enviar_email_admin(dest, 'Recordatorio de pago — Lumini', _plantilla_html(asunto='Recordatorio de pago', cuerpo=cuerpo, alerta=True))
                    enviados += 1
            exito = f'Recordatorios enviados a {enviados} colegio(s).'

        elif accion == 'enviar_actualizacion':
            version = request.form.get('version', '').strip()
            novedades = request.form.get('novedades', '').strip()
            slugs = request.form.getlist('slugs')
            email_global = request.form.get('email_global', '').strip()
            if not version or not novedades:
                error = 'Versión y novedades son requeridas.'
            else:
                cuerpo = (
                    f'<b>Versión:</b> {version}<br><br>'
                    f'<b>¿Qué hay de nuevo?</b><br>{novedades.replace(chr(10), "<br>")}'
                )
                destinos = []
                if email_global:
                    destinos.append(email_global)
                for s in slugs:
                    row = cm.execute('SELECT email FROM colegios WHERE slug=?', (s,)).fetchone()
                    if row and row['email']:
                        destinos.append(row['email'])
                for d in destinos:
                    _enviar_email_admin(d, f'Actualización Lumini — {version}', _plantilla_html(asunto=f'Novedades: {version}', cuerpo=cuerpo))
                exito = f'Notificación enviada a {len(destinos)} destinatario(s).'

        elif accion == 'enviar_promocional':
            institucion = request.form.get('institucion', '').strip()
            email = request.form.get('email', '').strip()
            asunto = request.form.get('asunto', '').strip()
            mensaje = request.form.get('mensaje', '').strip()
            if not email or not asunto:
                error = 'Correo y asunto son requeridos.'
            else:
                _enviar_email_admin(email, asunto, _plantilla_html(asunto=asunto, cuerpo=mensaje.replace(chr(10), '<br>')))
                exito = f'Correo promocional enviado a {email}.'

        elif accion == 'enviar_lista':
            lista_raw = request.form.get('lista_emails', '').strip()
            asunto = request.form.get('asunto', '').strip()
            mensaje = request.form.get('mensaje', '').strip()
            emails = [e.strip() for e in lista_raw.split('\n') if e.strip()]
            if not emails or not asunto:
                error = 'Lista de correos y asunto son requeridos.'
            else:
                for e in emails:
                    _enviar_email_admin(e, asunto, _plantilla_html(asunto=asunto, cuerpo=mensaje.replace(chr(10), '<br>')))
                exito = f'Correo enviado a {len(emails)} contacto(s).'

        elif accion == 'enviar_individual':
            email = request.form.get('email', '').strip()
            asunto = request.form.get('asunto', '').strip()
            mensaje = request.form.get('mensaje', '').strip()
            if not email or not asunto:
                error = 'Correo y asunto son requeridos.'
            else:
                _enviar_email_admin(email, asunto, _plantilla_html(asunto=asunto, cuerpo=mensaje.replace(chr(10), '<br>')))
                exito = f'Correo enviado a {email}.'

        elif accion == 'reenviar_bienvenida':
            slug = request.form.get('slug', '').strip()
            email = request.form.get('email', '').strip()
            row = cm.execute('SELECT nombre FROM colegios WHERE slug=?', (slug,)).fetchone()
            if not row:
                error = 'Colegio no encontrado.'
            elif not email:
                error = 'Correo destino requerido.'
            else:
                cuerpo = (
                    f'¡Bienvenido a Lumini!<br><br>'
                    f'A partir de ahora, <b>{row["nombre"]}</b> podrá gestionar notas, asistencia y '
                    f'comunicación escolar desde nuestra plataforma.<br><br>'
                    f'No duden en contactarnos si tienen dudas.<br><br>'
                    f'— Equipo Lumini'
                )
                _enviar_email_admin(email, 'Bienvenido a Lumini', _plantilla_html(asunto='Bienvenido a Lumini', cuerpo=cuerpo))
                exito = f'Correo de bienvenida reenviado a {email}.'

        elif accion == 'enviar_correo':
            exito = 'Función de correo genérico disponible. Usa las opciones del Centro de Correos.'

        else:
            error = f'Acción "{accion}" no reconocida.'

    except Exception as e:
        logger.exception('Error en admin_correos_handler')
        error = f'Error al procesar: {str(e)}'

    cm.close()
    return render_template('admin_correos.html', colegios=colegios, error=error, exito=exito)


def _enviar_email_admin(destino, asunto, cuerpo_html):
    ok = enviar_correo(destino, asunto, cuerpo_html)
    if ok:
        logger.info(f'Correo enviado a {destino}: {asunto}')
    else:
        logger.warning(f'Correo no enviado a {destino} (SendGrid no configurado). Asunto: {asunto}')
    return ok


def _plantilla_html(asunto, cuerpo, alerta=False):
    color = '#f59e0b' if alerta else '#6366f1'
    return f'''<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#0f0f1a;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px;">
<table width="560" cellpadding="0" cellspacing="0" style="background:#1a1a2e;border-radius:16px;overflow:hidden;">
<tr><td style="padding:32px 32px 16px;text-align:center;border-bottom:1px solid #2a2a3e;">
<h1 style="color:#fff;font-size:20px;font-weight:800;margin:0;letter-spacing:-.3px;">LUMINI</h1>
<p style="color:#8888aa;font-size:11px;margin:4px 0 0;letter-spacing:2px;text-transform:uppercase;">{asunto}</p>
</td></tr>
<tr><td style="padding:24px 32px;color:#ccc;font-size:14px;line-height:1.6;">
{cuerpo}
</td></tr>
<tr><td style="padding:16px 32px 24px;text-align:center;border-top:1px solid #2a2a3e;">
<p style="color:#555;font-size:11px;margin:0;">© Lumini — Plataforma de Gestión Académica</p>
</td></tr>
</table>
</td></tr></table>
</body></html>'''
