"""Admin routes (super-admin panels).

During Phase 1, routes remain defined in flask_app.py.
This blueprint will gradually absorb admin routes.
"""

from app.routes import admin_bp


@admin_bp.record_once
def _warn(state):
    import logging
    logging.getLogger(__name__).info(
        "Admin blueprint registered — routes pending migration from flask_app.py"
    )
