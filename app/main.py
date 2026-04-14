from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from .config import settings
from .routers import (
    auth_router,
    pets_router,
    chat_router,
    adoption_router,
    upload_router,
    notifications_router,
    dev_router,
)

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PetMatch API",
    description="Backend para PetMatch - Encontrá la pareja ideal para tu mascota",
    version="1.0.0",
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


@app.get("/health")
def health():
    return {"status": "ok", "service": "PetMatch API"}
