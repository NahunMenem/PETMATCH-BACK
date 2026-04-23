from sqlalchemy import inspect, text

from .database import engine


def run_startup_migrations() -> None:
    inspector = inspect(engine)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    adoption_columns = {
        column["name"] for column in inspector.get_columns("adoptions")
    }
    table_names = set(inspector.get_table_names())
    pet_like_columns = (
        {column["name"] for column in inspector.get_columns("pet_likes")}
        if "pet_likes" in table_names
        else set()
    )

    with engine.begin() as conn:
        if "patitas" not in user_columns:
            conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN patitas INTEGER NOT NULL DEFAULT 0"
                )
            )
        if "referral_code" not in user_columns:
            conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN referral_code VARCHAR"
                )
            )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_referral_code "
                "ON users (referral_code)"
            )
        )
        if "referred_by_user_id" not in user_columns:
            conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN referred_by_user_id VARCHAR REFERENCES users(id)"
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
        if "patitas_packs" not in table_names:
            conn.execute(
                text(
                    "CREATE TABLE patitas_packs ("
                    "id VARCHAR PRIMARY KEY, "
                    "name VARCHAR NOT NULL, "
                    "price INTEGER NOT NULL, "
                    "base_patitas INTEGER NOT NULL, "
                    "bonus_patitas INTEGER NOT NULL DEFAULT 0, "
                    "is_active BOOLEAN NOT NULL DEFAULT TRUE, "
                    "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
        conn.execute(
            text(
                "INSERT INTO patitas_packs (id, name, price, base_patitas, bonus_patitas, is_active) "
                "VALUES "
                "('starter', 'Starter', 3000, 100, 0, TRUE), "
                "('popular', 'Popular', 6000, 250, 25, TRUE), "
                "('pro', 'Pro', 10000, 500, 100, TRUE) "
                "ON CONFLICT (id) DO NOTHING"
            )
        )
        if "pet_likes" in table_names and "is_super_like" not in pet_like_columns:
            conn.execute(
                text(
                    "ALTER TABLE pet_likes "
                    "ADD COLUMN is_super_like BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
        conn.execute(
            text(
                "UPDATE users "
                "SET referral_code = UPPER(SUBSTRING(REPLACE(id, '-', '') FROM 1 FOR 8)) "
                "WHERE referral_code IS NULL"
            )
        )
