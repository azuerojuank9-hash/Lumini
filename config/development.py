from config.base import BaseSettings


class DevelopmentSettings(BaseSettings):
    ENV: str = 'development'
    SEND_FILE_MAX_AGE_DEFAULT: int = 86400
    SESSION_COOKIE_SECURE: bool = False
    PORT: int = 5000
