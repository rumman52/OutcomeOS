import logging
import time

import psycopg
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql://outcomeos:outcomeos@localhost:5432/outcomeos"
    worker_poll_interval_seconds: float = 5.0


def check_database(database_url: str) -> None:
    """Fail startup unless the worker's required database is reachable."""
    with psycopg.connect(database_url, connect_timeout=2) as connection:
        connection.execute("SELECT 1")


def run() -> None:
    """Run the worker shell until a real queue consumer replaces the idle loop."""
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    check_database(settings.database_url)
    logger.info("worker ready")
    while True:
        time.sleep(settings.worker_poll_interval_seconds)
