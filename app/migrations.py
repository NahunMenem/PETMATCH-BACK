from sqlalchemy import inspect, text

from .database import engine


def run_startup_migrations() -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        table_names = set(inspector.get_table_names())
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        adoption_columns = {
            column["name"] for column in inspector.get_columns("adoptions")
        }
        lost_pet_columns = {
            column["name"] for column in inspector.get_columns("lost_pets")
        }
        pet_like_columns = (
            {column["name"] for column in inspector.get_columns("pet_likes")}
            if "pet_likes" in table_names
            else set()
        )

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
        if "apple_id" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN apple_id VARCHAR"))
            conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_apple_id ON users (apple_id)")
            )
        if "terms_accepted_at" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN terms_accepted_at TIMESTAMP"))
        if "phone" not in adoption_columns:
            conn.execute(
                text(
                    "ALTER TABLE adoptions "
                    "ADD COLUMN phone VARCHAR NOT NULL DEFAULT ''"
                )
            )
        if "sex" not in adoption_columns:
            conn.execute(text("ALTER TABLE adoptions ADD COLUMN sex VARCHAR"))
        if "sex" not in lost_pet_columns:
            conn.execute(text("ALTER TABLE lost_pets ADD COLUMN sex VARCHAR"))
        if "phone" not in lost_pet_columns:
            conn.execute(
                text(
                    "ALTER TABLE lost_pets "
                    "ADD COLUMN phone VARCHAR NOT NULL DEFAULT ''"
                )
            )
        if "photos" not in lost_pet_columns:
            conn.execute(
                text(
                    "ALTER TABLE lost_pets "
                    "ADD COLUMN photos VARCHAR[] DEFAULT ARRAY[]::VARCHAR[]"
                )
            )
        if "location" not in lost_pet_columns:
            conn.execute(
                text(
                    "ALTER TABLE lost_pets "
                    "ADD COLUMN location VARCHAR NOT NULL DEFAULT ''"
                )
            )
        if "latitude" not in lost_pet_columns:
            conn.execute(text("ALTER TABLE lost_pets ADD COLUMN latitude FLOAT"))
        if "longitude" not in lost_pet_columns:
            conn.execute(text("ALTER TABLE lost_pets ADD COLUMN longitude FLOAT"))
        if "reward_amount" not in lost_pet_columns:
            conn.execute(text("ALTER TABLE lost_pets ADD COLUMN reward_amount INTEGER"))
        if "alert_radius_km" not in lost_pet_columns:
            conn.execute(text("ALTER TABLE lost_pets ADD COLUMN alert_radius_km INTEGER"))
        if "last_notified_at" not in lost_pet_columns:
            conn.execute(text("ALTER TABLE lost_pets ADD COLUMN last_notified_at TIMESTAMP"))
        if "status" not in lost_pet_columns:
            conn.execute(
                text(
                    "ALTER TABLE lost_pets "
                    "ADD COLUMN status VARCHAR NOT NULL DEFAULT 'active'"
                )
            )
        if "reported_at" not in lost_pet_columns:
            conn.execute(
                text(
                    "ALTER TABLE lost_pets "
                    "ADD COLUMN reported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                )
            )
        if "updated_at" not in lost_pet_columns:
            conn.execute(
                text(
                    "ALTER TABLE lost_pets "
                    "ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
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
        else:
            conn.execute(
                text(
                    "ALTER TABLE patitas_packs "
                    "ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE patitas_packs "
                    "ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP"
                )
            )
        if "content_reports" not in table_names:
            conn.execute(
                text(
                    "CREATE TABLE content_reports ("
                    "id VARCHAR PRIMARY KEY, "
                    "reporter_id VARCHAR NOT NULL REFERENCES users(id), "
                    "reported_user_id VARCHAR REFERENCES users(id), "
                    "content_type VARCHAR NOT NULL, "
                    "content_id VARCHAR NOT NULL, "
                    "reason TEXT NOT NULL, "
                    "status VARCHAR NOT NULL DEFAULT 'pending', "
                    "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            conn.execute(text("CREATE INDEX ix_content_reports_reporter_id ON content_reports (reporter_id)"))
            conn.execute(text("CREATE INDEX ix_content_reports_reported_user_id ON content_reports (reported_user_id)"))
            conn.execute(text("CREATE INDEX ix_content_reports_content_id ON content_reports (content_id)"))
        if "user_blocks" not in table_names:
            conn.execute(
                text(
                    "CREATE TABLE user_blocks ("
                    "id VARCHAR PRIMARY KEY, "
                    "blocker_id VARCHAR NOT NULL REFERENCES users(id), "
                    "blocked_user_id VARCHAR NOT NULL REFERENCES users(id), "
                    "reason TEXT, "
                    "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            conn.execute(text("CREATE INDEX ix_user_blocks_blocker_id ON user_blocks (blocker_id)"))
            conn.execute(text("CREATE INDEX ix_user_blocks_blocked_user_id ON user_blocks (blocked_user_id)"))
        conn.execute(
            text(
                "UPDATE patitas_packs "
                "SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP), "
                "updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP) "
                "WHERE created_at IS NULL OR updated_at IS NULL"
            )
        )
        conn.execute(
            text(
                "INSERT INTO patitas_packs ("
                "id, name, price, base_patitas, bonus_patitas, is_active, created_at, updated_at"
                ") "
                "VALUES "
                "('starter', 'Starter', 3000, 100, 0, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
                "('popular', 'Popular', 6000, 250, 25, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
                "('pro', 'Pro', 10000, 500, 100, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
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
