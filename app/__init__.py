import os

from dotenv import load_dotenv
from flask import Flask

_basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(_basedir, '.env'))

def create_app(config_name=None):
    app = Flask(__name__)
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400 * 7
    _raw_secret = (os.environ.get('SECRET_KEY') or '').strip()
    if not _raw_secret:
        raise RuntimeError("SECRET_KEY no esta definido en .env")
    app.secret_key = _raw_secret
    app.config['JSON_AS_ASCII'] = False
    return app
