import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


def initialize_database(max_attempts: int = 5) -> None:
    delay_seconds = 2
    for attempt in range(1, max_attempts + 1):
        try:
            Base.metadata.create_all(bind=engine)
            run_startup_migrations()
            logger.info("Database initialized successfully")
            return
        except SQLAlchemyError:
            logger.exception(
                "Database initialization failed on attempt %s/%s",
                attempt,
                max_attempts,
            )
            if attempt == max_attempts:
                logger.error("Starting API without database initialization")
                return
            time.sleep(delay_seconds)
            delay_seconds = min(delay_seconds * 2, 15)

app = FastAPI(
    title="PetMatch API",
    description="Backend para PetMatch - Encontrá la pareja ideal para tu mascota",
    version="1.0.0",
)


@app.on_event("startup")
def startup_event():
    initialize_database()

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
