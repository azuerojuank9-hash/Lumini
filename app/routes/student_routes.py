"""Student routes.

During Phase 1, routes remain defined in flask_app.py.
This blueprint will gradually absorb student routes.
"""

from app.routes import student_bp


@student_bp.record_once
def _warn(state):
    import logging
    logging.getLogger(__name__).info(
        "Student blueprint registered — routes pending migration from flask_app.py"
    )
