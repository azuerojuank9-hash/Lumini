import os

from config.base import BaseSettings
from config.development import DevelopmentSettings
from config.production import ProductionSettings
from config.testing import TestingSettings

_ENV_MAP = {
    'development': DevelopmentSettings,
    'testing': TestingSettings,
    'production': ProductionSettings,
}


def get_settings() -> BaseSettings:
    env = os.environ.get('FLASK_ENV', 'production')
    cls = _ENV_MAP.get(env, ProductionSettings)
    return cls()


settings = get_settings()
