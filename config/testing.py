from config.base import BaseSettings


class TestingSettings(BaseSettings):
    ENV: str = 'testing'
    SEND_FILE_MAX_AGE_DEFAULT: int = 0
    SESSION_COOKIE_SECURE: bool = False
    PORT: int = 5000
