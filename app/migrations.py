from sqlalchemy import inspect, text

from .database import engine


def run_startup_migrations() -> None:
    inspector = inspect(engine)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    adoption_columns = {
        column["name"] for column in inspector.get_columns("adoptions")
    }

    with engine.begin() as conn:
        if "patitas" not in user_columns:
            conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN patitas INTEGER NOT NULL DEFAULT 0"
                )
            )
        if "phone" not in adoption_columns:
            conn.execute(
                text(
                    "ALTER TABLE adoptions "
                    "ADD COLUMN phone VARCHAR NOT NULL DEFAULT ''"
                )
            )
