"""Main/general routes — login, public pages, etc.

During Phase 1, routes remain defined in flask_app.py.
This blueprint will gradually absorb the ~60 ungrouped @app.route endpoints.
"""

from flask import Blueprint

main_bp = Blueprint('main', __name__)


@main_bp.record_once
def _warn(state):
    import logging
    logging.getLogger(__name__).info(
        "Main blueprint registered — routes pending migration from flask_app.py"
    )
