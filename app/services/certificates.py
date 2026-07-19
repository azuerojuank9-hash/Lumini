"""Certificate generation service — re-exports from existing utils/certificates.py."""

import sys
import os

_basedir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, _basedir)

from utils.certificates import *  # noqa: F401, E402
