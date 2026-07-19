"""Route Blueprints — organized by role/domain.

All blueprints are created here and can be registered in the app factory
or in flask_app.py for backward compatibility.
"""

from flask import Blueprint

rector_bp = Blueprint('rector', __name__, url_prefix='/rector')
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
parent_bp = Blueprint('parent', __name__, url_prefix='/padre')
student_bp = Blueprint('student', __name__, url_prefix='/estudiante')

# API v1 blueprint is registered from api/v1/auth.py
from flask import current_app
api_v1_available = False
try:
    from api.v1.auth import bp as api_v1_bp
    api_v1_available = True
except ImportError:
    api_v1_bp = None

from app.routes import rector_routes  # noqa: F401, E402
from app.routes import admin_routes  # noqa: F401, E402
from app.routes import parent_routes  # noqa: F401, E402
from app.routes import student_routes  # noqa: F401, E402
from app.routes import main_routes  # noqa: F401, E402


__all__ = [
    'rector_bp', 'admin_bp', 'parent_bp', 'student_bp',
    'api_v1_bp', 'api_v1_available',
]
