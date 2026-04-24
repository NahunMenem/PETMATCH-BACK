import math
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user
from ..database import get_db

ADMIN_EMAIL = "nahundeveloper@gmail.com"

router = APIRouter(tags=["shops"])


# ─── Admin dependency ─────────────────────────────────────────────────────────

def get_admin_user(current_user: models.User = Depends(get_current_user)):
    if current_user.email != ADMIN_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido al administrador",
        )
    return current_user


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ShopCreate(BaseModel):
    nombre: str
    tipo: str
    descripcion: Optional[str] = None
    direccion: str
    lat: float
    lng: float
    telefono_whatsapp: Optional[str] = None
    rating: Optional[float] = None
    promo: Optional[str] = None
    es_destacado: bool = False
    es_aliado: bool = False
    activo: bool = True
    foto_url: Optional[str] = None


class ShopUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    descripcion: Optional[str] = None
    direccion: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    telefono_whatsapp: Optional[str] = None
    rating: Optional[float] = None
    promo: Optional[str] = None
    es_destacado: Optional[bool] = None
    es_aliado: Optional[bool] = None
    activo: Optional[bool] = None
    foto_url: Optional[str] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in km between two lat/lng points using the Haversine formula."""
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return round(radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)


def _shop_to_dict(shop: models.Shop, distance_km: Optional[float] = None) -> dict:
    return {
        "id": shop.id,
        "nombre": shop.nombre,
        "tipo": shop.tipo,
        "descripcion": shop.descripcion,
        "direccion": shop.direccion,
        "lat": shop.lat,
        "lng": shop.lng,
        "telefono_whatsapp": shop.telefono_whatsapp,
        "rating": shop.rating,
        "promo": shop.promo,
        "es_destacado": shop.es_destacado,
        "es_aliado": shop.es_aliado,
        "activo": shop.activo,
        "foto_url": shop.foto_url,
        "distance_km": distance_km,
    }


# ─── Public endpoints ─────────────────────────────────────────────────────────

@router.get("/shops/cercanos")
def get_shops_cercanos(
    lat: float = Query(..., description="Latitud del usuario"),
    lng: float = Query(..., description="Longitud del usuario"),
    tipo: Optional[str] = Query(None, description="Filtrar por tipo de comercio"),
    search: Optional[str] = Query(None, description="Buscar por nombre o descripcion"),
    radio_km: float = Query(10.0, description="Radio de busqueda en km"),
    db: Session = Depends(get_db),
):
    query = db.query(models.Shop).filter(models.Shop.activo == True)

    if tipo:
        query = query.filter(models.Shop.tipo == tipo)

    if search:
        term = f"%{search.lower()}%"
        query = query.filter(
            models.Shop.nombre.ilike(term) | models.Shop.descripcion.ilike(term)
        )

    shops = query.all()

    results = []
    for shop in shops:
        distance = _haversine_km(lat, lng, shop.lat, shop.lng)
        if distance <= radio_km:
            results.append((shop, distance))

    # Sort: destacados first, then by distance ascending
    results.sort(key=lambda x: (not x[0].es_destacado, x[1]))

    return [_shop_to_dict(shop, distance) for shop, distance in results]


@router.get("/shops/{shop_id}")
def get_shop(
    shop_id: str,
    db: Session = Depends(get_db),
):
    shop = db.query(models.Shop).filter(
        models.Shop.id == shop_id,
        models.Shop.activo == True,
    ).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    return _shop_to_dict(shop)


# ─── Admin endpoints ──────────────────────────────────────────────────────────

@router.post("/admin/shops", status_code=status.HTTP_201_CREATED)
def create_shop(
    payload: ShopCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_admin_user),
):
    shop = models.Shop(
        nombre=payload.nombre.strip(),
        tipo=payload.tipo.strip(),
        descripcion=payload.descripcion.strip() if payload.descripcion else None,
        direccion=payload.direccion.strip(),
        lat=payload.lat,
        lng=payload.lng,
        telefono_whatsapp=payload.telefono_whatsapp,
        rating=payload.rating,
        promo=payload.promo,
        es_destacado=payload.es_destacado,
        es_aliado=payload.es_aliado,
        activo=payload.activo,
        foto_url=payload.foto_url,
    )
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return _shop_to_dict(shop)


@router.put("/admin/shops/{shop_id}")
def update_shop(
    shop_id: str,
    payload: ShopUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_admin_user),
):
    shop = db.query(models.Shop).filter(models.Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")

    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(shop, field, value)

    shop.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(shop)
    return _shop_to_dict(shop)


@router.delete("/admin/shops/{shop_id}", status_code=status.HTTP_200_OK)
def delete_shop(
    shop_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_admin_user),
):
    shop = db.query(models.Shop).filter(models.Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")

    shop.activo = False
    shop.updated_at = datetime.utcnow()
    db.commit()
    return {"detail": "Comercio desactivado correctamente", "id": shop_id}
