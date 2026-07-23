"""Authentication service — login, logout, password recovery, brute-force."""

import logging
import secrets

from app.infra.session import clear as session_clear
from app.infra.session import set as session_set
from app.infra.session import set_permanent

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


def login_estudiante(slug, codigo, password, alumno, verificar_pw=None, necesita_rehash=None, hash_pw=None):
    if not alumno:
        return None, 'Código de estudiante no encontrado.'
    if not alumno['activo']:
        return None, 'El estudiante no está activo.'
    if alumno['pin'] and password != alumno['pin']:
        return None, 'PIN incorrecto.'
    session_clear()
    set_permanent(True)
    session_set(f'alumno_id_{slug}', alumno['id'])
    return 'estudiante', None


def parent_portal_login(slug, email, pin, get_parent_fn, get_children_fn):
    parent = get_parent_fn(slug, email, pin)
    if not parent:
        return None, 'Credenciales incorrectas.'
    session_clear()
    set_permanent(True)
    session_set(f'padre_id_{slug}', parent['id'])
    children = get_children_fn(slug, parent['id'])
    return {'padre': dict(parent), 'hijos': [dict(c) for c in children]}, None


def validate_password_change(actual, nueva, confirmar, prof, verificar_pw):
    if not actual or not nueva or not confirmar:
        return 'Todos los campos son obligatorios.'
    if not verificar_pw(actual, prof['password']):
        return 'La contraseña actual es incorrecta.'
    if len(nueva) < 6:
        return 'La nueva contraseña debe tener al menos 6 caracteres.'
    if nueva != confirmar:
        return 'Las contraseñas nuevas no coinciden.'
    if actual == nueva:
        return 'La nueva contraseña debe ser diferente a la actual.'
    return None


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
