"""Rector/Administrator routes.

During Phase 1, routes remain defined in flask_app.py.
This blueprint will gradually absorb rector-grade routes.
"""

from app.routes import rector_bp


@rector_bp.record_once
def _warn(state):
    import logging
    logging.getLogger(__name__).info(
        "Rector blueprint registered — routes pending migration from flask_app.py"
    )
