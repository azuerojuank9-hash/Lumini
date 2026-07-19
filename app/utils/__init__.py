"""Shared utility functions.

Re-exports from existing utils/ modules and flask_app.py.
"""

from app.utils.security import (
    hash_pw,
    verificar_pw,
    necesita_rehash,
    generar_csrf,
    validar_csrf,
    extension_permitida,
    validar_imagen,
)
from app.utils.bruteforce import (
    ip_bloqueada,
    registrar_fallo,
    limpiar_intentos,
)

__all__ = [
    'hash_pw', 'verificar_pw', 'necesita_rehash',
    'generar_csrf', 'validar_csrf',
    'extension_permitida', 'validar_imagen',
    'ip_bloqueada', 'registrar_fallo', 'limpiar_intentos',
]
