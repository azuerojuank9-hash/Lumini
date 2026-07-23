"""Certificate generation service — re-exports from existing utils/certificates.py."""

import os
import sys

_basedir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, _basedir)

from utils.certificates import (  # noqa: F401, E402
    generar_constancia_estudio,
    generar_certificado_estudio,
    generar_paz_y_salvo,
    generar_certificado_conducta,
)
