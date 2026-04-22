from sqlalchemy import inspect, text

from .database import engine


def run_startup_migrations() -> None:
    inspector = inspect(engine)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    adoption_columns = {
        column["name"] for column in inspector.get_columns("adoptions")
    }
    table_names = set(inspector.get_table_names())

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
        if "device_tokens" not in table_names:
            conn.execute(
                text(
                    "CREATE TABLE device_tokens ("
                    "id VARCHAR PRIMARY KEY, "
                    "user_id VARCHAR NOT NULL REFERENCES users(id), "
                    "token VARCHAR NOT NULL UNIQUE, "
                    "platform VARCHAR, "
                    "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            conn.execute(
                text("CREATE INDEX ix_device_tokens_token ON device_tokens (token)")
            )
