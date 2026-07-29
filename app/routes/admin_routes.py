from flask import jsonify, redirect, render_template, request

from app.routes import admin_bp


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
def admin_correos_placeholder(accion=None):
    fa = _fa()
    if not fa.session.get('admin_auth'):
        return redirect(fa.url_for('auth.admin'))
    return 'Esta funcionalidad esta en desarrollo.', 501
