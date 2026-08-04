"""Authentication routes — login, logout, password recovery for all roles."""

import logging

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# ── Imports from flask_app (shared helpers — will be extracted as modules migrate) ──
def _import_flask_app():
    import flask_app
    return flask_app

def _colegio(slug):
    fa = _import_flask_app()
    fa.require_colegio(slug)
    return fa.get_colegio(slug)


@auth_bp.route('/admin', methods=['GET', 'POST'])
def admin():
    fa = _import_flask_app()
    error = exito = None
    ip = request.remote_addr

    if not session.get('admin_auth'):
        if request.method == 'POST' and request.form.get('accion') == 'admin_login':
            if not fa.validar_csrf():
                error = 'Error de seguridad.'
                return render_template('admin_login.html', error=error)
            bloqueado = fa.ip_bloqueada(ip, prefijo='admin')
            if bloqueado:
                error = f'Demasiados intentos. Espera {bloqueado}s.'
                return render_template('admin_login.html', error=error)
            from app.services.auth_service import login_admin
            rol, err = login_admin(
                request.form.get('password', ''),
                fa.ADMIN_PASSWORD,
                ip,
                fa.limpiar_intentos,
                fa.registrar_fallo
            )
            if err:
                error = err
                return render_template('admin_login.html', error=error)
            return redirect(url_for('auth.admin'))
        return render_template('admin_login.html', error=error)

    import os

    from app.models.schema import conectar_master, db_path, init_db
    from app.repositories.user_repository import (
        create_colegio,
        delete_colegio,
        get_all_colegios,
        toggle_colegio_activo,
    )
    from app.utils.security import extension_permitida, validar_imagen

    colegios = get_all_colegios()

    if request.method == 'POST':
        if not fa.validar_csrf():
            return redirect(url_for('auth.admin'))
        accion = request.form.get('accion')

        if accion == 'crear_colegio':
            nombre = request.form.get('nombre', '').strip()
            slug = request.form.get('slug', '').strip().lower().replace(' ', '-')
            num_p = request.form.get('num_periodos', 4, type=int)
            venc = request.form.get('vencimiento', '').strip() or None
            codigo = request.form.get('codigo_registro', '').strip()
            pri_col = request.form.get('primary_color', '#6c63ff').strip()
            sec_col = request.form.get('secondary_color', '#3498db').strip()
            if not nombre or not slug:
                error = 'Nombre y slug son obligatorios.'
            elif not slug.replace('-', '').isalnum():
                error = 'El slug solo puede tener letras, numeros y guiones.'
            elif not codigo:
                error = 'El codigo de invitacion es obligatorio.'
            else:
                logo_filename = ''
                if 'logo' in request.files:
                    f = request.files['logo']
                    if f and f.filename:
                        if not extension_permitida(f.filename):
                            error = 'Solo se permiten imagenes (png, jpg, jpeg, gif, webp).'
                        else:
                            ext = f.filename.rsplit('.', 1)[-1].lower()
                            logo_filename = f'{slug}.{ext}'
                            ruta_logo = os.path.join(fa.LOGO_FOLDER, logo_filename)
                            f.save(ruta_logo)
                            if not validar_imagen(ruta_logo):
                                os.remove(ruta_logo)
                                error = 'El archivo no es una imagen valida.'
                                logo_filename = ''
                if not error:
                    from app.repositories.user_repository import create_colegio
                    try:
                        create_colegio(slug, nombre, logo_filename, num_p, venc, codigo, pri_col, sec_col)
                    except Exception:
                        logger.warning('register_colegio: slug duplicado %s', slug)
                        error = f'El slug "{slug}" ya existe.'
                    if not error:
                        init_db(slug)
                        exito = f'Colegio "{nombre}" creado. URL: /{slug}/login · Codigo: {codigo}'
                        logger.info(f'Colegio creado: {slug}')

        elif accion == 'toggle_colegio':
            slug_t = request.form.get('slug')
            toggle_colegio_activo(slug_t)
            return redirect(url_for('auth.admin'))

        elif accion == 'editar_colegio':
            slug_e = request.form.get('slug', '').strip().lower()
            if not slug_e.replace('-', '').isalnum():
                error = 'Slug invalido.'
                return render_template('admin_panel.html', error=error, exito=exito, colegios=colegios)
            nombre = request.form.get('nombre', '').strip()
            num_p = request.form.get('num_periodos', 4, type=int)
            venc = request.form.get('vencimiento', '').strip() or None
            codigo = request.form.get('codigo_registro', '').strip()
            pri_col = request.form.get('primary_color', '#6c63ff').strip()
            sec_col = request.form.get('secondary_color', '#3498db').strip()
            cm = conectar_master()
            cm.execute('''UPDATE colegios SET nombre=?, num_periodos=?, vencimiento=?, codigo_registro=?,
                          codigo_profesores=?, codigo_directoras=?, codigo_rectores=?, primary_color=?, secondary_color=?
                          WHERE slug=?''',
                       (nombre, num_p, venc, codigo, codigo, codigo, codigo, pri_col, sec_col, slug_e))
            cm.commit()
            if 'logo' in request.files:
                f = request.files['logo']
                if f and f.filename:
                    if not extension_permitida(f.filename):
                        error = 'Solo se permiten imagenes (png, jpg, jpeg, gif, webp).'
                    else:
                        ext = f.filename.rsplit('.', 1)[-1].lower()
                        logo_filename = f'{slug_e}.{ext}'
                        ruta_logo = os.path.join(fa.LOGO_FOLDER, logo_filename)
                        f.save(ruta_logo)
                        if not validar_imagen(ruta_logo):
                            os.remove(ruta_logo)
                            error = 'El archivo no es una imagen valida.'
                        else:
                            cm.execute('UPDATE colegios SET logo=? WHERE slug=?', (logo_filename, slug_e))
                            cm.commit()
            cm.close()
            fa._cache_invalidate(slug_e)
            fa._cache_invalidate(prefix='col_')
            exito = f'Colegio "{nombre}" actualizado. Codigo: {codigo}'

        elif accion == 'eliminar_colegio':
            slug_e = request.form.get('slug')
            delete_colegio(slug_e)
            if os.path.exists(db_path(slug_e)):
                os.rename(db_path(slug_e), db_path(slug_e) + '.bak')
            exito = 'Colegio eliminado.'
            logger.info(f'Colegio eliminado: {slug_e}')

        colegios = get_all_colegios()

    return render_template('admin_panel.html', colegios=colegios, error=error, exito=exito)


@auth_bp.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('auth.admin'))


@auth_bp.route('/<slug>/recuperar', methods=['GET', 'POST'])
def recuperar_password(slug):
    fa = _import_flask_app()
    fa.require_colegio(slug)
    colegio = fa.get_colegio(slug)
    error = exito = None
    pregunta = None
    usuario_val = ''
    paso = 1
    ip = request.remote_addr

    if request.method == 'POST':
        if not fa.validar_csrf():
            error = 'Error de seguridad. Intenta de nuevo.'
            return render_template('recuperar.html', slug=slug, colegio=colegio, error=error, exito=exito, pregunta=pregunta, usuario_val=usuario_val, paso=paso)
        bloqueado = fa.ip_bloqueada(ip, prefijo=f'recup_{slug}')
        if bloqueado:
            error = f'Demasiados intentos. Espera {bloqueado}s.'
            return render_template('recuperar.html', slug=slug, colegio=colegio, error=error, exito=exito, pregunta=pregunta, usuario_val=usuario_val, paso=paso)
        accion = request.form.get('accion', '')
        usuario_val = request.form.get('usuario', '').strip()

        if accion == 'buscar_usuario':
            from app.repositories.user_repository import find_profesor_by_username
            prof = find_profesor_by_username(slug, usuario_val)
            if not prof:
                error = 'Usuario no encontrado.'
                fa.registrar_fallo(ip, prefijo=f'recup_{slug}')
            elif not prof['pregunta_secreta']:
                error = 'Este usuario no tiene pregunta secreta. Contacta al administrador.'
                fa.registrar_fallo(ip, prefijo=f'recup_{slug}')
            else:
                pregunta = prof['pregunta_secreta']
                paso = 2

        elif accion == 'cambiar_password':
            respuesta = request.form.get('respuesta', '').strip().lower()
            nueva = request.form.get('nueva', '').strip()
            confirmar = request.form.get('confirmar', '').strip()
            from app.repositories.user_repository import find_profesor_by_username, update_profesor_password
            prof = find_profesor_by_username(slug, usuario_val)
            if not prof:
                error = 'Usuario no encontrado.'
                fa.registrar_fallo(ip, prefijo=f'recup_{slug}')
            elif prof['respuesta_secreta'].lower() != respuesta:
                error = 'Respuesta incorrecta.'
                pregunta = prof['pregunta_secreta']; paso = 2
                fa.registrar_fallo(ip, prefijo=f'recup_{slug}')
            elif len(nueva) < 6:
                error = 'Minimo 6 caracteres.'
                pregunta = prof['pregunta_secreta']; paso = 2
                fa.registrar_fallo(ip, prefijo=f'recup_{slug}')
            elif nueva != confirmar:
                error = 'Las contrasenas no coinciden.'
                pregunta = prof['pregunta_secreta']; paso = 2
                fa.registrar_fallo(ip, prefijo=f'recup_{slug}')
            else:
                from app.utils.security import hash_pw
                update_profesor_password(slug, prof['id'], hash_pw(nueva))
                exito = 'Contrasena actualizada. Ya puedes ingresar.'
                fa.limpiar_intentos(ip, prefijo=f'recup_{slug}')

    return render_template('recuperar.html',
                           slug=slug, colegio=colegio, error=error, exito=exito,
                           pregunta=pregunta, usuario_val=usuario_val, paso=paso)


@auth_bp.route('/<slug>/directora/buscar_usuario_recuperar', methods=['POST'])
def directora_buscar_usuario_recuperar(slug):
    fa = _import_flask_app()
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'mensaje': 'Error CSRF'})
    fa.require_colegio(slug)
    ip = request.remote_addr
    bloqueado = fa.ip_bloqueada(ip, prefijo=f'recup_directora_{slug}')
    if bloqueado:
        return jsonify({'ok': False, 'mensaje': f'Demasiados intentos. Espera {bloqueado}s.'})
    usuario = request.form.get('usuario', '').strip()
    from app.repositories.user_repository import find_directora_by_username
    d = find_directora_by_username(slug, usuario)
    if not d:
        fa.registrar_fallo(ip, prefijo=f'recup_directora_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Usuario no encontrado.'})
    if not d['pregunta_secreta']:
        fa.registrar_fallo(ip, prefijo=f'recup_directora_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Este usuario no tiene pregunta secreta.'})
    return jsonify({'ok': True, 'pregunta': d['pregunta_secreta']})


@auth_bp.route('/<slug>/directora/cambiar_password_recuperar', methods=['POST'])
def directora_cambiar_password_recuperar(slug):
    fa = _import_flask_app()
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'mensaje': 'Error CSRF'})
    fa.require_colegio(slug)
    ip = request.remote_addr
    bloqueado = fa.ip_bloqueada(ip, prefijo=f'recup_directora_{slug}')
    if bloqueado:
        return jsonify({'ok': False, 'mensaje': f'Demasiados intentos. Espera {bloqueado}s.'})
    data = request.get_json(silent=True) or {}
    usuario = data.get('usuario', '') or request.form.get('usuario', '')
    usuario = usuario.strip()
    respuesta = data.get('respuesta', '') or request.form.get('respuesta', '')
    respuesta = respuesta.strip().lower()
    nueva = data.get('nueva_password', '') or request.form.get('nueva', '')
    nueva = nueva.strip()
    from app.repositories.user_repository import find_directora_by_username, update_directora_password
    d = find_directora_by_username(slug, usuario)
    if not d:
        fa.registrar_fallo(ip, prefijo=f'recup_directora_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Usuario no encontrado.'})
    if not d['respuesta_secreta'] or d['respuesta_secreta'].lower() != respuesta:
        fa.registrar_fallo(ip, prefijo=f'recup_directora_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Respuesta incorrecta.'})
    if len(nueva) < 6:
        fa.registrar_fallo(ip, prefijo=f'recup_directora_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Minimo 6 caracteres.'})
    from app.utils.security import hash_pw
    update_directora_password(slug, d['id'], hash_pw(nueva))
    fa.limpiar_intentos(ip, prefijo=f'recup_directora_{slug}')
    return jsonify({'ok': True, 'mensaje': 'Contrasena actualizada. Ya puedes ingresar.'})


@auth_bp.route('/<slug>/login', methods=['GET', 'POST'], endpoint='login')
def login(slug):
    fa = _import_flask_app()
    fa.require_colegio(slug)
    fa.init_db(slug)
    colegio = fa.get_colegio(slug)
    error = None
    ip = request.remote_addr

    if request.method == 'POST':
        if not fa.validar_csrf():
            error = 'Error de seguridad.'
            return render_template('login_v2.html', error=error, materias=fa.MATERIAS,
                                   jornadas=fa.JORNADAS, preguntas=fa.PREGUNTAS_SECRETAS,
                                   slug=slug, colegio=colegio)
        accion = request.form.get('accion')

        if accion == 'profesor_login':
            bloqueado = fa.ip_bloqueada(ip, prefijo=slug)
            if bloqueado:
                error = f'Demasiados intentos. Espera {bloqueado}s.'
                return render_template('login_v2.html', error=error, materias=fa.MATERIAS,
                                       jornadas=fa.JORNADAS, preguntas=fa.PREGUNTAS_SECRETAS,
                                       slug=slug, colegio=colegio)
            u = request.form.get('usuario', '').strip()
            p = request.form.get('password', '').strip()
            if not p:
                error = 'La contrasena es obligatoria.'
            else:
                from app.repositories.user_repository import find_profesor_by_username
                prof = find_profesor_by_username(slug, u)
                from app.services.auth_service import login_profesor
                rol, err = login_profesor(slug, u, p, prof, fa.verificar_pw, fa.necesita_rehash, fa.hash_pw)
                if err:
                    fa.registrar_fallo(ip, prefijo=slug)
                    error = err
                else:
                    fa.limpiar_intentos(ip, prefijo=slug)
                    return redirect(url_for('teacher.seleccionar_jornada', slug=slug))

        elif accion == 'profesor_registro':
            nombre = request.form.get('nombre', '').strip()
            usuario = request.form.get('reg_usuario', '').strip()
            pw = request.form.get('reg_password', '').strip()
            email_p = request.form.get('email_prof', '').strip()
            pregunta = request.form.get('pregunta_secreta', '').strip()
            respuesta = request.form.get('respuesta_secreta', '').strip()
            materias_sel = request.form.getlist('materias_sel')
            jornadas_sel = request.form.getlist('jornadas_sel')
            codigo = request.form.get('codigo_registro', '').strip()
            confirmar = request.form.get('confirmar_password', '').strip()
            codigo_colegio = fa.get_codigo_registro(slug, 'profesores')
            if pw != confirmar:
                error = 'Las contrasenas no coinciden.'
            elif codigo_colegio and codigo != codigo_colegio:
                error = 'Codigo de invitacion incorrecto.'
            elif not nombre or not usuario or not email_p:
                error = 'Completa todos los campos obligatorios.'
            elif len(pw) < 6:
                error = 'Minimo 6 caracteres.'
            elif not pregunta or not respuesta:
                error = 'Debes elegir una pregunta secreta y escribir tu respuesta.'
            elif not materias_sel:
                error = 'Agrega al menos una materia con su jornada.'
            else:
                from app.repositories.user_repository import create_profesor, username_exists_profesor
                if username_exists_profesor(slug, usuario):
                    error = 'Ese usuario ya existe.'
                else:
                    from app.utils.security import hash_pw
                    pid = create_profesor(slug, nombre, usuario, hash_pw(pw), email_p, pregunta, respuesta.lower())
                    from app.models.schema import conectar
                    conn = conectar(slug)
                    for mat, jor in zip(materias_sel, jornadas_sel):
                        if mat and jor:
                            try:
                                conn.execute(
                                    'INSERT OR IGNORE INTO asignaciones_materia (profesor_id,materia,jornada) VALUES (?,?,?)',
                                    (pid, mat, jor))
                            except Exception as e:
                                logger.warning(f'Error al asignar materia={mat} jornada={jor} a profesor={pid} en {slug}: {e}')
                    conn.commit(); conn.close()
                    error = 'Registro exitoso. Ya puedes ingresar.'

        elif accion == 'estudiante':
            ip = request.remote_addr or '0.0.0.0'
            bloqueo = fa.ip_bloqueada(ip, prefijo=f'est_{slug}')
            if bloqueo:
                error = f'Demasiados intentos. Espera {bloqueo} segundos.'
            else:
                nombre = request.form.get('nombre_est', '').strip().lower()
                jornada = request.form.get('jornada_est', '').strip()
                pin_ingresado = request.form.get('pin_est', '').strip()
                from app.repositories.user_repository import find_alumno_by_nombre
                alumno = find_alumno_by_nombre(slug, nombre, jornada)
                from app.services.auth_service import login_estudiante
                rol, err = login_estudiante(slug, nombre, pin_ingresado, alumno, fa.verificar_pw, fa.necesita_rehash, fa.hash_pw)
                if err:
                    fa.registrar_fallo(ip, prefijo=f'est_{slug}')
                    error = err
                else:
                    fa.limpiar_intentos(ip, prefijo=f'est_{slug}')
                    return redirect(url_for('student.vista_estudiante', slug=slug))

        elif accion == 'directora_login':
            ip = request.remote_addr or '0.0.0.0'
            bloqueo = fa.ip_bloqueada(ip, prefijo=f'dir_{slug}')
            if bloqueo:
                error = f'Demasiados intentos. Espera {bloqueo} segundos.'
            else:
                u = request.form.get('dir_usuario', '').strip()
                p = request.form.get('dir_password', '').strip()
                from app.repositories.user_repository import find_directora_by_username
                d = find_directora_by_username(slug, u)
                from app.services.auth_service import login_directora
                rol, err = login_directora(slug, u, p, d, fa.verificar_pw)
                if err:
                    fa.registrar_fallo(ip, prefijo=f'dir_{slug}')
                    error = err
                else:
                    fa.limpiar_intentos(ip, prefijo=f'dir_{slug}')
                    return redirect(url_for('directora.directora_panel', slug=slug))

        elif accion == 'rector_login':
            bloqueado = fa.ip_bloqueada(ip, prefijo=f'rec_{slug}')
            if bloqueado:
                error = f'Demasiados intentos. Espera {bloqueado}s.'
                return render_template('login_v2.html', error=error, materias=fa.MATERIAS,
                                       jornadas=fa.JORNADAS, preguntas=fa.PREGUNTAS_SECRETAS,
                                       slug=slug, colegio=colegio)
            u = request.form.get('rec_usuario', '').strip()
            p = request.form.get('rec_password', '').strip()
            from app.repositories.user_repository import find_rector_by_username
            rector = find_rector_by_username(slug, u)
            from app.services.auth_service import login_rector
            rol, err = login_rector(slug, u, p, rector, fa.verificar_pw)
            if err:
                fa.registrar_fallo(ip, prefijo=f'rec_{slug}')
                error = err
            else:
                fa.limpiar_intentos(ip, prefijo=f'rec_{slug}')
                return redirect(url_for('rector.rector_panel', slug=slug))

    return render_template('login_v2.html', error=error, materias=fa.MATERIAS,
                           jornadas=fa.JORNADAS, preguntas=fa.PREGUNTAS_SECRETAS,
                           slug=slug, colegio=colegio)


@auth_bp.route('/<slug>/logout')
def logout(slug):
    session.clear()
    return redirect(url_for('auth.login', slug=slug))


@auth_bp.route('/<slug>/cambiar_password', methods=['GET', 'POST'])
def cambiar_password(slug):
    fa = _import_flask_app()
    fa.require_colegio(slug)
    prof = fa.get_profesor(slug)
    if not prof:
        return redirect(url_for('auth.login', slug=slug))
    jornada, materia = fa.get_sesion_jornada_materia(slug)
    error = exito = None
    if request.method == 'POST':
        if not fa.validar_csrf():
            error = 'Error de seguridad.'
        else:
            actual = request.form.get('actual', '').strip()
            nueva = request.form.get('nueva', '').strip()
            confirmar = request.form.get('confirmar', '').strip()
            from app.services.auth_service import validate_password_change
            err = validate_password_change(actual, nueva, confirmar, prof, fa.verificar_pw)
            if err:
                error = err
            else:
                from app.repositories.user_repository import update_profesor_password
                from app.utils.security import hash_pw
                update_profesor_password(slug, prof['id'], hash_pw(nueva))
                exito = 'Contrasena cambiada!'
    mis_cursos = fa.get_cursos_profesor(slug, prof['id'], materia, jornada)
    materias_jornadas = fa.get_materias_profesor(slug, prof['id'])
    colegio = fa.get_colegio(slug)
    return render_template('cambiar_password.html',
                           profesor=prof, mis_cursos=mis_cursos,
                           materias_jornadas=materias_jornadas,
                           error=error, exito=exito, slug=slug, colegio=colegio,
                           materia=materia, jornada=jornada)


@auth_bp.route('/<slug>/portal/login', methods=['GET', 'POST'])
def portal_padre_login(slug):
    fa = _import_flask_app()
    fa.require_colegio(slug)
    if request.method == 'GET':
        pid = session.get(f'padre_id_{slug}')
        if pid:
            conn = fa.conectar(slug)
            try:
                from app.services.parent_service import ParentService
                hijos = ParentService.get_dashboard_data(conn, pid)
                padre = conn.execute('SELECT * FROM padres WHERE id=?', (pid,)).fetchone()
            finally:
                conn.close()
            return render_template('portal_padre.html', slug=slug, colegio=fa.get_colegio(slug),
                                   step='dashboard', hijos=hijos, padre=padre)
        return render_template('portal_padre.html', slug=slug, colegio=fa.get_colegio(slug), step='login')
    ip = request.remote_addr or '0.0.0.0'
    if fa.ip_bloqueada(ip, prefijo=f'parent_{slug}'):
        return jsonify({'error': 'Demasiados intentos. Espera 5 minutos.'}), 429
    if not fa.validar_csrf():
        return jsonify({'error': 'CSRF inválido'}), 403
    data = request.get_json(silent=True) or request.form
    email = data.get('email', '').strip().lower()
    pin = data.get('pin', '').strip()
    if not email or not pin:
        return jsonify({'error': 'Email y PIN requeridos'}), 400
    from app.repositories.user_repository import get_children_for_parent, get_parent_by_email_pin
    from app.services.auth_service import parent_portal_login
    result, err = parent_portal_login(slug, email, pin, get_parent_by_email_pin, get_children_for_parent)
    if err:
        fa.registrar_fallo(ip, prefijo=f'parent_{slug}')
        return jsonify({'error': err}), 401
    fa.limpiar_intentos(ip, prefijo=f'parent_{slug}')
    return jsonify({'status': 'ok', **result})


# ── RECTOR AUTH ──────────────────────────────────────────────────────────────────

@auth_bp.route('/<slug>/rector/login', methods=['GET', 'POST'])
def rector_login(slug):
    fa = _import_flask_app()
    fa.require_colegio(slug)
    fa.init_db(slug)
    colegio = fa.get_colegio(slug)
    error = exito = None
    ip = request.remote_addr
    if request.method == 'POST':
        if not fa.validar_csrf():
            error = 'Error de seguridad.'
            return render_template('rector_login.html', slug=slug, colegio=colegio, error=error, exito=exito)
        bloqueado = fa.ip_bloqueada(ip, prefijo=f'rector_{slug}')
        if bloqueado:
            error = f'Demasiados intentos. Espera {bloqueado}s.'
            return render_template('rector_login.html', slug=slug, colegio=colegio, error=error, exito=exito)
        u = request.form.get('usuario', '').strip()
        p = request.form.get('password', '').strip()
        from app.repositories.user_repository import find_rector_by_username
        rector = find_rector_by_username(slug, u)
        from app.services.auth_service import login_rector
        rol, err = login_rector(slug, u, p, rector, fa.verificar_pw)
        if err:
            fa.registrar_fallo(ip, prefijo=f'rector_{slug}')
            error = err
        else:
            fa.limpiar_intentos(ip, prefijo=f'rector_{slug}')
            return redirect(url_for('rector.rector_panel', slug=slug))
    return render_template('rector_login.html', slug=slug, colegio=colegio,
                           error=error, exito=exito)


@auth_bp.route('/<slug>/rector/registrar', methods=['POST'])
def rector_registrar(slug):
    fa = _import_flask_app()
    if not fa.validar_csrf():
        return 'Error de seguridad', 400
    fa.require_colegio(slug)
    fa.init_db(slug)
    colegio = fa.get_colegio(slug)
    error = exito = None
    nombre = request.form.get('nombre', '').strip()
    usuario = request.form.get('usuario', '').strip()
    pw = request.form.get('password', '').strip()
    confirm = request.form.get('confirmar_password', '').strip()
    jornada = request.form.get('jornada', '').strip()
    email = request.form.get('email', '').strip()
    pregunta = request.form.get('pregunta_secreta', '').strip()
    resp = request.form.get('respuesta_secreta', '').strip().lower()
    codigo = request.form.get('codigo_registro_rec', '').strip()
    codigo_colegio = fa.get_codigo_registro(slug, 'rectores')
    if codigo_colegio and codigo != codigo_colegio:
        error = 'Codigo de invitacion incorrecto.'
    elif pw != confirm:
        error = 'Las contrasenas no coinciden.'
    elif not nombre or not usuario or not pw or not jornada:
        error = 'Completa todos los campos obligatorios.'
    elif len(pw) < 6:
        error = 'Minimo 6 caracteres.'
    elif not pregunta or not resp:
        error = 'Debes elegir una pregunta secreta y escribir tu respuesta.'
    else:
        from app.repositories.user_repository import create_rector, username_exists_rector
        if username_exists_rector(slug, usuario):
            error = 'Ese usuario ya existe. Elige otro nombre de usuario.'
        else:
            from app.utils.security import hash_pw
            create_rector(slug, nombre, usuario, hash_pw(pw), jornada, email, pregunta, resp)
            exito = 'Cuenta de Rector creada. Ya puedes ingresar.'
    return render_template('rector_login.html', slug=slug, colegio=colegio,
                           error=error, exito=exito)


@auth_bp.route('/<slug>/rector/buscar_usuario_recuperar', methods=['POST'])
def rector_buscar_usuario_recuperar(slug):
    fa = _import_flask_app()
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'mensaje': 'Error CSRF'})
    fa.require_colegio(slug)
    ip = request.remote_addr
    bloqueado = fa.ip_bloqueada(ip, prefijo=f'recup_rector_{slug}')
    if bloqueado:
        return jsonify({'ok': False, 'mensaje': f'Demasiados intentos. Espera {bloqueado}s.'})
    u = request.form.get('usuario', '').strip()
    from app.repositories.user_repository import find_rector_by_username
    r = find_rector_by_username(slug, u)
    if not r or not r['pregunta_secreta']:
        fa.registrar_fallo(ip, prefijo=f'recup_rector_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Usuario no encontrado.'})
    return jsonify({'ok': True, 'pregunta': r['pregunta_secreta']})


@auth_bp.route('/<slug>/rector/cambiar_password_recuperar', methods=['POST'])
def rector_cambiar_password_recuperar(slug):
    fa = _import_flask_app()
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'mensaje': 'Error CSRF'})
    fa.require_colegio(slug)
    ip = request.remote_addr
    bloqueado = fa.ip_bloqueada(ip, prefijo=f'recup_rector_{slug}')
    if bloqueado:
        return jsonify({'ok': False, 'mensaje': f'Demasiados intentos. Espera {bloqueado}s.'})
    data = request.get_json(silent=True) or {}
    u = data.get('usuario', '') or request.form.get('usuario', '')
    u = u.strip()
    rta = data.get('respuesta', '') or request.form.get('respuesta', '')
    rta = rta.strip().lower()
    nueva = data.get('nueva_password', '') or request.form.get('nueva', '')
    nueva = nueva.strip()
    from app.repositories.user_repository import find_rector_by_username, update_rector_password
    r = find_rector_by_username(slug, u)
    if not r:
        fa.registrar_fallo(ip, prefijo=f'recup_rector_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Usuario no encontrado.'})
    if not r['respuesta_secreta'] or r['respuesta_secreta'].lower() != rta:
        fa.registrar_fallo(ip, prefijo=f'recup_rector_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Respuesta incorrecta.'})
    if len(nueva) < 6:
        fa.registrar_fallo(ip, prefijo=f'recup_rector_{slug}')
        return jsonify({'ok': False, 'mensaje': 'Minimo 6 caracteres.'})
    from app.utils.security import hash_pw
    update_rector_password(slug, r['id'], hash_pw(nueva))
    fa.limpiar_intentos(ip, prefijo=f'recup_rector_{slug}')
    return jsonify({'ok': True, 'mensaje': 'Contrasena actualizada. Ya puedes ingresar.'})


@auth_bp.route('/<slug>/rector/logout')
def rector_logout(slug):
    session.clear()
    return redirect(url_for('auth.login', slug=slug))


# ── DIRECTORA AUTH ───────────────────────────────────────────────────────────────

@auth_bp.route('/<slug>/directora/login', methods=['GET', 'POST'])
def directora_login(slug):
    fa = _import_flask_app()
    fa.require_colegio(slug)
    colegio = fa.get_colegio(slug)
    error = exito = None
    ip = request.remote_addr
    if request.method == 'POST':
        if not fa.validar_csrf():
            error = 'Error de seguridad.'
            return render_template('directora_login.html', slug=slug, colegio=colegio, error=error, exito=exito)
        bloqueado = fa.ip_bloqueada(ip, prefijo=f'directora_{slug}')
        if bloqueado:
            error = f'Demasiados intentos. Espera {bloqueado}s.'
            return render_template('directora_login.html', slug=slug, colegio=colegio, error=error, exito=exito)
        u = request.form.get('usuario', '').strip()
        p = request.form.get('password', '').strip()
        from app.repositories.user_repository import find_directora_by_username
        d = find_directora_by_username(slug, u)
        from app.services.auth_service import login_directora
        rol, err = login_directora(slug, u, p, d, fa.verificar_pw)
        if err:
            fa.registrar_fallo(ip, prefijo=f'directora_{slug}')
            error = err
        else:
            fa.limpiar_intentos(ip, prefijo=f'directora_{slug}')
            return redirect(url_for('directora.directora_panel', slug=slug))
    return render_template('directora_login.html', slug=slug, colegio=colegio,
                           error=error, exito=exito)


@auth_bp.route('/<slug>/directora/registrar_directo', methods=['POST'])
def directora_registrar_directo(slug):
    fa = _import_flask_app()
    if not fa.validar_csrf():
        return 'Error de seguridad', 400
    fa.require_colegio(slug)
    fa.init_db(slug)
    colegio = fa.get_colegio(slug)
    error = exito = None
    nombre = request.form.get('nombre', '').strip()
    usuario = request.form.get('usuario', '').strip()
    pw = request.form.get('password', '').strip()
    confirmar = request.form.get('confirmar_password', '').strip()
    curso = request.form.get('curso', '').strip()
    jornada = request.form.get('jornada', '').strip()
    email = request.form.get('email', '').strip()
    pregunta = request.form.get('pregunta_secreta', '').strip()
    respuesta = request.form.get('respuesta_secreta', '').strip().lower()
    codigo = request.form.get('codigo_registro_dir', '').strip()
    codigo_colegio = fa.get_codigo_registro(slug, 'directoras')
    if codigo_colegio and codigo != codigo_colegio:
        error = 'Codigo de invitacion incorrecto.'
    elif pw != confirmar:
        error = 'Las contrasenas no coinciden.'
    elif not nombre or not usuario or not pw or not curso or not jornada:
        error = 'Completa todos los campos obligatorios.'
    elif len(pw) < 6:
        error = 'Minimo 6 caracteres.'
    elif not pregunta or not respuesta:
        error = 'Debes elegir una pregunta secreta y escribir tu respuesta.'
    else:
        from app.repositories.user_repository import create_directora, username_exists_directora
        if username_exists_directora(slug, usuario):
            error = 'Ese usuario ya existe. Elige otro nombre de usuario.'
        else:
            from app.utils.security import hash_pw
            create_directora(slug, nombre, usuario, hash_pw(pw), curso, jornada, email, pregunta, respuesta)
            exito = 'Cuenta creada. Ya puedes ingresar.'
    return render_template('directora_login.html', slug=slug, colegio=colegio,
                           error=error, exito=exito)


@auth_bp.route('/<slug>/directora/logout')
def directora_logout(slug):
    session.clear()
    return redirect(url_for('auth.directora_login', slug=slug))
