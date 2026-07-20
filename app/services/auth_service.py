"""Authentication service — login, logout, password recovery, brute-force."""

import secrets
import logging
from app.infra.session import clear as session_clear, set_permanent, set as session_set

logger = logging.getLogger(__name__)


def login_profesor(slug, usuario, password, prof, verificar_pw, necesita_rehash, hash_pw):
    if not prof or not verificar_pw(password, prof['password']):
        return None, 'Usuario o contraseña incorrectos.'
    if necesita_rehash(prof['password']):
        from app.repositories.user_repository import update_profesor_password
        update_profesor_password(slug, prof['id'], hash_pw(password))
        logger.info(f'Hash migrado para profesor id={prof["id"]} en {slug}')
    session_clear()
    set_permanent(True)
    session_set(f'rol_{slug}', 'profesor')
    session_set(f'profesor_id_{slug}', prof['id'])
    return 'profesor', None


def login_rector(slug, usuario, password, rector, verificar_pw):
    if not rector or not verificar_pw(password, rector['password']):
        return None, 'Usuario o contraseña incorrectos.'
    session_clear()
    set_permanent(True)
    session_set(f'rector_id_{slug}', rector['id'])
    return 'rector', None


def login_directora(slug, usuario, password, directora, verificar_pw):
    if not directora or not verificar_pw(password, directora['password']):
        return None, 'Usuario o contraseña incorrectos.'
    session_clear()
    set_permanent(True)
    session_set(f'directora_id_{slug}', directora['id'])
    return 'directora', None


def login_admin(password, admin_password, ip, limpiar_intentos_fn, registrar_fallo_fn):
    from flask import session
    if password == admin_password:
        limpiar_intentos_fn(ip, prefijo='admin')
        session.clear()
        session['admin_auth'] = True
        return True, None
    intentos = registrar_fallo_fn(ip, prefijo='admin')
    restantes = 5 - intentos
    if restantes <= 0:
        return False, 'Demasiados intentos. Cuenta bloqueada por 5 minutos.'
    return False, f'Contraseña incorrecta. Intentos restantes: {restantes}'


def admin_logout():
    from flask import session
    session.pop('admin_auth', None)


def login_estudiante(slug, codigo, password, alumno, verificar_pw, necesita_rehash, hash_pw):
    if not alumno:
        return None, 'Código de estudiante no encontrado.'
    if not alumno['activo']:
        return None, 'El estudiante no está activo.'
    if not verificar_pw(password, alumno['password']):
        return None, 'Contraseña incorrecta.'
    if necesita_rehash(alumno['password']):
        from app.repositories.user_repository import update_alumno_password
        update_alumno_password(slug, alumno['id'], hash_pw(password))
    session_clear()
    set_permanent(True)
    session_set(f'alumno_id_{slug}', alumno['id'])
    return 'estudiante', None


def recuperar_password(slug, usuario, tipo, preguntas, respuestas, get_prof, get_dir, get_rec, hash_pw_fn):
    if tipo == 'profesor':
        u = get_prof(slug)
    elif tipo == 'directora':
        u = get_dir(slug)
    elif tipo == 'rector':
        u = get_rec(slug)
    else:
        return False, 'Tipo de usuario no válido.'
    if not u:
        return False, 'Usuario no encontrado.'
    if not u.get('activo'):
        return False, 'Usuario inactivo.'
    for p, r in zip(preguntas, respuestas):
        if u.get(p) and str(u[p]).lower() != str(r).lower():
            return False, 'Respuesta incorrecta.'
    nueva = secrets.token_urlsafe(8)
    if tipo == 'profesor':
        from app.repositories.user_repository import update_profesor_password
        update_profesor_password(slug, u['id'], hash_pw_fn(nueva))
    elif tipo == 'directora':
        from app.repositories.user_repository import update_directora_password
        update_directora_password(slug, u['id'], hash_pw_fn(nueva))
    elif tipo == 'rector':
        from app.repositories.user_repository import update_rector_password
        update_rector_password(slug, u['id'], hash_pw_fn(nueva))
    return True, nueva
