from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    APP_ENV: str = "dev"
    LOG_LEVEL: str = "INFO"
    SCRAPE_BASE_URL: str = "https://books.toscrape.com"
    SCRAPE_CONCURRENCY: int = 8
    SCRAPE_TIMEOUT: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
