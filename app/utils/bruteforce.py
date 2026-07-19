"""Brute-force protection — login attempt tracking and IP blocking."""

import time
import logging

logger = logging.getLogger(__name__)

login_intentos = {}


def ip_bloqueada(ip, prefijo=''):
    clave = f'{prefijo}_{ip}'
    d = login_intentos.get(clave)
    if not d:
        return False
    if d['bloqueado_hasta'] and time.time() < d['bloqueado_hasta']:
        return int(d['bloqueado_hasta'] - time.time())
    return False


def registrar_fallo(ip, prefijo=''):
    _purgar_intentos_antiguos()
    clave = f'{prefijo}_{ip}'
    d = login_intentos.setdefault(clave, {'intentos': 0, 'bloqueado_hasta': None})
    d['intentos'] += 1
    if d['intentos'] >= 5:
        d['bloqueado_hasta'] = time.time() + 300
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
