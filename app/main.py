import logging
import threading
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import Base, engine
from .migrations import run_startup_migrations
from .config import settings
from .routers import (
    auth_router,
    pets_router,
    chat_router,
    adoption_router,
    upload_router,
    notifications_router,
    dev_router,
    patitas_router,
    lost_pets_router,
    admin_router,
    shops_router,
    app_router,
)

logger = logging.getLogger(__name__)


def initialize_database(max_attempts: int = 12) -> None:
    delay_seconds = 2
    for attempt in range(1, max_attempts + 1):
        try:
            Base.metadata.create_all(bind=engine)
            run_startup_migrations()
            logger.info("Database initialized successfully")
            return
        except SQLAlchemyError as exc:
            logger.warning(
                "Database initialization failed on attempt %s/%s: %s",
                attempt,
                max_attempts,
                exc,
            )
            if attempt == max_attempts:
                logger.exception("Database initialization failed after all attempts")
                return
            time.sleep(delay_seconds)
            delay_seconds = min(delay_seconds * 2, 15)


def initialize_database_in_background() -> None:
    thread = threading.Thread(target=initialize_database, daemon=True)
    thread.start()

app = FastAPI(
    title="PetMatch API",
    description="Backend para PetMatch - Encontrá la pareja ideal para tu mascota",
    version="1.0.0",
)


@app.on_event("startup")
def startup_event():
    initialize_database_in_background()


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(_request: Request, exc: SQLAlchemyError):
    logger.warning("Database request failed: %s", exc)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "La base de datos no esta disponible. Intenta de nuevo en unos segundos.",
        },
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In prod: settings.cors_origins_list
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router.router)
app.include_router(pets_router.router)
app.include_router(chat_router.router)
app.include_router(adoption_router.router)
app.include_router(upload_router.router)
app.include_router(notifications_router.router)
app.include_router(dev_router.router)
app.include_router(patitas_router.router)
app.include_router(lost_pets_router.router)
app.include_router(admin_router.router)
app.include_router(shops_router.router)
app.include_router(app_router.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "PetMatch API"}


@app.get("/health/db")
def database_health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
