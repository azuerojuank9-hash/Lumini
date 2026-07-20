from config.base import BaseSettings


class ProductionSettings(BaseSettings):
    ENV: str = 'production'
