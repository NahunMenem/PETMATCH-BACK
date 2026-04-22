import math
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..patitas_service import consumir_patitas


router = APIRouter(prefix="/lost-pets", tags=["lost-pets"])

ALERT_RADIUS_ACTIONS = {
    2: "lost_notification_2km",
    5: "lost_notification_5km",
}


def _distance_km(
    lat1: Optional[float],
    lng1: Optional[float],
    lat2: Optional[float],
    lng2: Optional[float],
) -> Optional[float]:
    if None in (lat1, lng1, lat2, lng2):
        return None

    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return round(radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)


def _lost_pet_to_out(
    lost_pet: models.LostPet,
    current_user: Optional[models.User] = None,
) -> schemas.LostPetOut:
    distance = None
    if current_user:
        distance = _distance_km(
            current_user.latitude,
            current_user.longitude,
            lost_pet.latitude,
            lost_pet.longitude,
        )

    return schemas.LostPetOut(
        id=lost_pet.id,
        reporter_id=lost_pet.reporter_id,
        reporter_name=lost_pet.reporter.name if lost_pet.reporter else "",
        reporter_photo=lost_pet.reporter.photo_url if lost_pet.reporter else None,
        pet_id=lost_pet.pet_id,
        name=lost_pet.name,
        type=lost_pet.type.value,
        description=lost_pet.description,
        phone=lost_pet.phone,
        photos=lost_pet.photos or [],
        location=lost_pet.location,
        latitude=lost_pet.latitude,
        longitude=lost_pet.longitude,
        reward_amount=lost_pet.reward_amount,
        alert_radius_km=lost_pet.alert_radius_km,
        status=lost_pet.status.value,
        reported_at=lost_pet.reported_at,
        distance_km=distance,
    )


@router.get("", response_model=List[schemas.LostPetOut])
def list_lost_pets(
    page: int = Query(1, ge=1),
    status_filter: Optional[str] = Query("active", alias="status"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.LostPet)
    if status_filter in {status_item.value for status_item in models.LostPetStatus}:
        query = query.filter(models.LostPet.status == models.LostPetStatus(status_filter))

    lost_pets = (
        query.order_by(models.LostPet.reported_at.desc())
        .offset((page - 1) * 20)
        .limit(20)
        .all()
    )
    return [_lost_pet_to_out(lost_pet, current_user) for lost_pet in lost_pets]


@router.get("/mine", response_model=List[schemas.LostPetOut])
def list_my_lost_pets(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    lost_pets = (
        db.query(models.LostPet)
        .filter(models.LostPet.reporter_id == current_user.id)
        .order_by(models.LostPet.reported_at.desc())
        .all()
    )
    return [_lost_pet_to_out(lost_pet, current_user) for lost_pet in lost_pets]


@router.post("", response_model=schemas.LostPetOut, status_code=status.HTTP_201_CREATED)
def create_lost_pet(
    payload: schemas.LostPetCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if payload.type not in {models.PetType.dog.value, models.PetType.cat.value}:
        raise HTTPException(status_code=400, detail="Tipo de mascota invalido")

    pet = None
    if payload.pet_id:
        pet = (
            db.query(models.Pet)
            .filter(models.Pet.id == payload.pet_id, models.Pet.owner_id == current_user.id)
            .first()
        )
        if not pet:
            raise HTTPException(status_code=404, detail="Mascota no encontrada")

    if payload.alert_radius_km not in (None, 2, 5):
        raise HTTPException(status_code=400, detail="Radio de alerta invalido")

    photos = payload.photos or []
    if not photos and pet:
        photos = pet.photos or []

    if pet:
        pet.is_active = False

    lost_pet = models.LostPet(
        reporter_id=current_user.id,
        pet_id=payload.pet_id,
        name=payload.name.strip(),
        type=models.PetType(payload.type),
        description=payload.description.strip(),
        phone=payload.phone.strip(),
        photos=photos,
        location=payload.location.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        reward_amount=payload.reward_amount,
        alert_radius_km=payload.alert_radius_km,
    )
    db.add(lost_pet)
    if payload.alert_radius_km:
        consumir_patitas(
            db,
            current_user,
            ALERT_RADIUS_ACTIONS[payload.alert_radius_km],
            descripcion=f"Alerta de mascota perdida a {payload.alert_radius_km} km",
        )
    else:
        db.commit()
    db.refresh(lost_pet)
    return _lost_pet_to_out(lost_pet, current_user)


@router.patch("/{lost_pet_id}/status", response_model=schemas.LostPetOut)
def update_lost_pet_status(
    lost_pet_id: str,
    payload: schemas.LostPetStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    lost_pet = (
        db.query(models.LostPet)
        .filter(models.LostPet.id == lost_pet_id, models.LostPet.reporter_id == current_user.id)
        .first()
    )
    if not lost_pet:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    if payload.status not in {status_item.value for status_item in models.LostPetStatus}:
        raise HTTPException(status_code=400, detail="Estado invalido")

    lost_pet.status = models.LostPetStatus(payload.status)
    db.commit()
    db.refresh(lost_pet)
    return _lost_pet_to_out(lost_pet, current_user)
