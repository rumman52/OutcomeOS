import uuid

import psycopg

from outcomeos_api.config import get_settings


def main() -> None:
    """Insert an idempotent local-development example outcome."""
    with psycopg.connect(get_settings().database_url) as connection:
        connection.execute(
            """INSERT INTO outcomes (id, title)
               SELECT %s, %s WHERE NOT EXISTS (SELECT 1 FROM outcomes WHERE title = %s)""",
            (uuid.uuid4(), "Ship the OutcomeOS foundation", "Ship the OutcomeOS foundation"),
        )


if __name__ == "__main__":
    main()
