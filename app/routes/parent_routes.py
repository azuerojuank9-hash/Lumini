"""Parent/Guardian routes.

During Phase 1, routes remain defined in flask_app.py.
This blueprint will gradually absorb parent routes.
"""

from app.routes import parent_bp


@parent_bp.record_once
def _warn(state):
    import logging
    logging.getLogger(__name__).info(
        "Parent blueprint registered — routes pending migration from flask_app.py"
    )
