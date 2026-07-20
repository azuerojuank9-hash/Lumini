import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

from app.logging.request_logger import RequestIdFilter

_basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_LOG_DIR = os.path.join(_basedir, 'logs')

_initialized = False


def _ensure_log_dir():
    os.makedirs(_LOG_DIR, exist_ok=True)
    os.makedirs(os.path.join(_LOG_DIR, 'errors'), exist_ok=True)
    os.makedirs(os.path.join(_LOG_DIR, 'security'), exist_ok=True)
    os.makedirs(os.path.join(_LOG_DIR, 'audit'), exist_ok=True)


def _init_root_logger():
    global _initialized
    if _initialized:
        return
    _ensure_log_dir()

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    fmt = '%(asctime)s [%(levelname)-7s] [%(request_id)s] %(name)s: %(message)s'

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(fmt))
    console.addFilter(RequestIdFilter())
    root.addHandler(console)

    app_handler = TimedRotatingFileHandler(
        os.path.join(_LOG_DIR, 'app.log'),
        when='midnight', interval=1, backupCount=30, encoding='utf-8',
    )
    app_handler.setLevel(logging.DEBUG)
    app_handler.setFormatter(logging.Formatter(fmt))
    app_handler.addFilter(RequestIdFilter())
    root.addHandler(app_handler)

    error_handler = TimedRotatingFileHandler(
        os.path.join(_LOG_DIR, 'errors', 'error.log'),
        when='midnight', interval=1, backupCount=90, encoding='utf-8',
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(logging.Formatter(fmt))
    error_handler.addFilter(RequestIdFilter())
    root.addHandler(error_handler)

    security_handler = TimedRotatingFileHandler(
        os.path.join(_LOG_DIR, 'security', 'security.log'),
        when='midnight', interval=1, backupCount=90, encoding='utf-8',
    )
    security_handler.setLevel(logging.INFO)
    security_handler.setFormatter(logging.Formatter(fmt))
    security_handler.addFilter(RequestIdFilter())
    root.addHandler(security_handler)

    # Suppress noisy libs
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    _initialized = True


def get_logger(name: str = __name__) -> logging.Logger:
    _init_root_logger()
    return logging.getLogger(name)


def get_security_logger() -> logging.Logger:
    _init_root_logger()
    return logging.getLogger('lumini.security')


def get_audit_logger() -> logging.Logger:
    _init_root_logger()
    return logging.getLogger('lumini.audit')
