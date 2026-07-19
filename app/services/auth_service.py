"""Authentication service — login, logout, password recovery, brute-force."""

import secrets
import logging
from datetime import timedelta
from flask import session

logger = logging.getLogger(__name__)


def login_profesor(slug, usuario, password, prof, verificar_pw, necesita_rehash, hash_pw):
    if not prof or not verificar_pw(password, prof['password']):
        return None, 'Usuario o contraseña incorrectos.'
    if necesita_rehash(prof['password']):
        from app.repositories.user_repository import update_profesor_password
        update_profesor_password(slug, prof['id'], hash_pw(password))
        logger.info(f'Hash migrado para profesor id={prof["id"]} en {slug}')
    session.clear()
    session.permanent = True
    session[f'rol_{slug}'] = 'profesor'
    session[f'profesor_id_{slug}'] = prof['id']
    return 'profesor', None


def login_rector(slug, usuario, password, rector, verificar_pw):
    if not rector or not verificar_pw(password, rector['password']):
        return None, 'Usuario o contraseña incorrectos.'
    session.clear()
    session.permanent = True
    session[f'rector_id_{slug}'] = rector['id']
    return 'rector', None


def login_directora(slug, usuario, password, directora, verificar_pw):
    if not directora or not verificar_pw(password, directora['password']):
        return None, 'Usuario o contraseña incorrectos.'
    session.clear()
    session.permanent = True
    session[f'directora_id_{slug}'] = directora['id']
    return 'directora', None


def login_estudiante(slug, nombre, jornada, pin_ingresado, alumno):
    if not alumno:
        return None, 'No se encontró ese estudiante.'
    if alumno['pin'] and pin_ingresado != alumno['pin']:
        return None, 'PIN incorrecto.'
    session.clear()
    session.permanent = True
    session[f'rol_{slug}'] = 'estudiante'
    session[f'alumno_id_{slug}'] = alumno['id']
    return 'estudiante', None


def admin_login(password, admin_password, ip, limpiar_intentos, registrar_fallo):
    if not secrets.compare_digest(password, admin_password):
        registrar_fallo(ip, prefijo='admin')
        logger.warning(f'Admin login fallido desde {ip}')
        return None, 'Contraseña incorrecta.'
    session.clear()
    session.permanent = True
    session['admin_auth'] = True
    limpiar_intentos(ip, prefijo='admin')
    logger.info(f'Admin login exitoso desde {ip}')
    return 'admin', None


def parent_portal_login(slug, email, pin, get_parent_fn, get_children_fn):
    padre = get_parent_fn(slug, email, pin)
    if not padre:
        return None, 'Credenciales inválidas'
    hijos = get_children_fn(slug, padre['id'])
    session[f'padre_id_{slug}'] = padre['id']
    session[f'rol_{slug}'] = 'padre'
    return {'padre': {'nombre': padre['nombre'], 'email': padre['email']},
            'hijos': [dict(h) for h in hijos]}, None


def validate_password_change(actual_password, nueva, confirmar, prof, verificar_pw):
    if not verificar_pw(actual_password, prof['password']):
        return 'Contraseña actual incorrecta.'
    if len(nueva) < 6:
        return 'Mínimo 6 caracteres.'
    if nueva != confirmar:
        return 'Las contraseñas no coinciden.'
    return None


def validate_password_recovery(prof, respuesta, nueva, confirmar, respuesta_guardada):
    if not prof:
        return 'Usuario no encontrado.', None, 1
    if not prof['pregunta_secreta']:
        return 'Este usuario no tiene pregunta secreta.', None, 1
    if respuesta and respuesta_guardada.lower() != respuesta:
        return 'Respuesta incorrecta.', prof['pregunta_secreta'], 2
    if nueva and len(nueva) < 6:
        return 'Mínimo 6 caracteres.', prof['pregunta_secreta'], 2
    if nueva and nueva != confirmar:
        return 'Las contraseñas no coinciden.', prof['pregunta_secreta'], 2
    return None, None, None


def set_session_for_rol(slug, rol, user_id):
    session.clear()
    session.permanent = True
    if rol == 'profesor':
        session[f'rol_{slug}'] = 'profesor'
        session[f'profesor_id_{slug}'] = user_id
    elif rol == 'rector':
        session[f'rector_id_{slug}'] = user_id
    elif rol == 'directora':
        session[f'directora_id_{slug}'] = user_id
    elif rol == 'estudiante':
        session[f'rol_{slug}'] = 'estudiante'
        session[f'alumno_id_{slug}'] = user_id
