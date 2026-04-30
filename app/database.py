from urllib.parse import parse_qs, urlparse

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .config import settings


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _connect_args(url: str) -> dict:
    parsed = urlparse(url)
    if not parsed.scheme.startswith("postgresql"):
        return {}

    query = parse_qs(parsed.query)
    hostname = parsed.hostname or ""
    is_local = hostname in {"localhost", "127.0.0.1", "::1"}
    args = {
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }
    if not is_local and "sslmode" not in query:
        args["sslmode"] = "require"
    return args


DATABASE_URL = _normalize_database_url(settings.DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=30,
    connect_args=_connect_args(DATABASE_URL),
)


@event.listens_for(engine, "connect")
def set_database_timezone(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SET TIME ZONE %s", (settings.APP_TIMEZONE,))
    finally:
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
