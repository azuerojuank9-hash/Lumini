"""Route Blueprints — organized by role/domain.

All blueprints are created here and can be registered in the app factory
or in flask_app.py for backward compatibility.
"""

from flask import Blueprint

rector_bp = Blueprint('rector', __name__)
directora_bp = Blueprint('directora', __name__)
admin_bp = Blueprint('admin', __name__)
parent_bp = Blueprint('parent', __name__)
student_bp = Blueprint('student', __name__)
notifications_bp = Blueprint('notifications', __name__)
channels_bp = Blueprint('channels', __name__)
files_bp = Blueprint('files', __name__)

# API v1 blueprint is registered from api/v1/auth.py
from flask import current_app

api_v1_available = False
try:
    from api.v1.auth import bp as api_v1_bp
    api_v1_available = True
except ImportError:
    api_v1_bp = None

from app.routes import (
    admin_routes,  # noqa: F401, E402
    channels_routes,  # noqa: F401, E402
    directora_routes,  # noqa: F401, E402
    files_routes,  # noqa: F401, E402
    main_routes,  # noqa: F401, E402
    notifications_routes,  # noqa: F401, E402
    parent_routes,  # noqa: F401, E402
    rector_routes,  # noqa: F401, E402
    student_routes,  # noqa: F401, E402
    teacher,  # noqa: F401, E402
)
from app.routes.attendance import attendance_bp  # noqa: F401, E402
from app.routes.courses import courses_bp  # noqa: F401, E402
from app.routes.observations import observations_bp  # noqa: F401, E402
from app.routes.teacher import teacher_bp  # noqa: F401, E402

__all__ = [
    'rector_bp', 'directora_bp', 'admin_bp', 'parent_bp', 'student_bp', 'notifications_bp', 'teacher_bp',
    'observations_bp', 'courses_bp', 'attendance_bp', 'channels_bp', 'files_bp',
    'api_v1_bp', 'api_v1_available',
]
