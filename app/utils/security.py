"""Security utilities — password hashing, CSRF, file validation."""

import hashlib
import logging
import secrets

logger = logging.getLogger(__name__)

import bcrypt
from flask import request, session


def hash_pw(pw, _sal=None):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verificar_pw(plano, guardada):
    if not guardada:
        return False
    if guardada.startswith('$2b$') or guardada.startswith('$2a$'):
        return bcrypt.checkpw(plano.encode(), guardada.encode())
    if '$' in guardada:
        partes = guardada.split('$', 1)
        if len(partes) == 2:
            sal, h = partes
            return hashlib.sha256((sal + plano).encode()).hexdigest() == h
        return False
    return hashlib.sha256(plano.encode()).hexdigest() == guardada


def necesita_rehash(guardada):
    return not (guardada.startswith('$2b$') or guardada.startswith('$2a$'))


def generar_csrf():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def validar_csrf():
    token = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
    return bool(token and token == session.get('_csrf_token'))


def extension_permitida(filename):
    ext = ('.' + filename.rsplit('.', 1)[-1]).lower() if '.' in filename else ''
    return ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp')


def validar_imagen(ruta):
    try:
        from PIL import Image
        img = Image.open(ruta)
        img.verify()
        return True
    except Exception:
        logger.debug('validar_imagen: imagen inválida %s', ruta)
        return False
