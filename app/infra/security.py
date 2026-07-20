import time, hashlib, bcrypt, secrets
from flask import session, request

login_intentos = {}


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
        return False


def ip_bloqueada(ip, prefijo=''):
    clave = f'{prefijo}_{ip}'
    d = login_intentos.get(clave)
    if not d:
        return False
    if d['bloqueado_hasta'] and time.time() < d['bloqueado_hasta']:
        return int(d['bloqueado_hasta'] - time.time())
    return False


def registrar_fallo(ip, prefijo='', logger=None):
    _purgar_intentos_antiguos()
    clave = f'{prefijo}_{ip}'
    d = login_intentos.setdefault(clave, {'intentos': 0, 'bloqueado_hasta': None})
    d['intentos'] += 1
    if d['intentos'] >= 5:
        d['bloqueado_hasta'] = time.time() + 300
        if logger:
            logger.warning(f"IP bloqueada por fuerza bruta: {ip} (ctx={prefijo})")
    return d['intentos']


def _purgar_intentos_antiguos():
    ahora = time.time()
    viejas = [k for k, v in login_intentos.items()
              if v['bloqueado_hasta'] and ahora > v['bloqueado_hasta'] + 3600]
    for k in viejas:
        del login_intentos[k]


def limpiar_intentos(ip, prefijo=''):
    login_intentos.pop(f'{prefijo}_{ip}', None)


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
