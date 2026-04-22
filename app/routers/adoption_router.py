import uuid
import math
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..auth import get_current_user
from ..notification_service import TYPE_ADOPTION_INTEREST, create_notification

router = APIRouter(prefix="/adoptions", tags=["adoptions"])


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


def _adoption_to_out(
    adoption: models.Adoption,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> schemas.AdoptionOut:
    pub = adoption.publisher
    distance = _distance_km(latitude, longitude, adoption.latitude, adoption.longitude)
    return schemas.AdoptionOut(
        id=adoption.id,
        publisher_id=adoption.publisher_id,
        publisher_name=pub.name,
        publisher_photo=pub.photo_url,
        name=adoption.name,
        type=adoption.type.value,
        age=adoption.age,
        breed=adoption.breed,
        size=adoption.size.value,
        health_status=adoption.health_status,
        description=adoption.description,
        photos=adoption.photos or [],
        location=adoption.location,
        latitude=adoption.latitude,
        longitude=adoption.longitude,
        distance_km=distance,
        phone=adoption.phone or "",
        status=adoption.status.value,
        published_at=adoption.published_at,
    )


@router.get("", response_model=List[schemas.AdoptionOut])
def get_adoptions(
    type: Optional[str] = Query(None),
    max_distance: Optional[int] = Query(None),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    age: Optional[str] = Query(None),
    size: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.Adoption).filter(
        models.Adoption.status == models.AdoptionStatus.available
    )

    if type in ("dog", "cat"):
        query = query.filter(models.Adoption.type == type)
    if size:
        query = query.filter(models.Adoption.size == size)

    adoptions = query.order_by(models.Adoption.published_at.desc()) \
        .offset((page - 1) * 20).limit(20).all()
    user_lat = lat if lat is not None else current_user.latitude
    user_lng = lng if lng is not None else current_user.longitude
    items = [_adoption_to_out(a, latitude=user_lat, longitude=user_lng) for a in adoptions]
    if max_distance is not None and user_lat is not None and user_lng is not None:
        items = [
            item
            for item in items
            if item.distance_km is not None and item.distance_km <= max_distance
        ]
    return items


@router.get("/mine", response_model=List[schemas.AdoptionOut])
def get_my_adoptions(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    adoptions = (
        db.query(models.Adoption)
        .filter(models.Adoption.publisher_id == current_user.id)
        .order_by(models.Adoption.published_at.desc())
        .all()
    )
    return [_adoption_to_out(a, latitude=current_user.latitude, longitude=current_user.longitude) for a in adoptions]


@router.post("", response_model=schemas.AdoptionOut, status_code=status.HTTP_201_CREATED)
def create_adoption(
    data: schemas.AdoptionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.type not in ("dog", "cat"):
        raise HTTPException(status_code=400, detail="Tipo de mascota inválido")
    if data.size not in ("small", "medium", "large"):
        raise HTTPException(status_code=400, detail="Tamaño inválido")

    if not data.phone.strip():
        raise HTTPException(status_code=400, detail="Telefono requerido")

    adoption = models.Adoption(
        id=str(uuid.uuid4()),
        publisher_id=current_user.id,
        name=data.name,
        type=data.type,
        age=data.age,
        breed=data.breed,
        size=data.size,
        health_status=data.health_status,
        description=data.description,
        photos=data.photos,
        location=data.location,
        latitude=data.latitude,
        longitude=data.longitude,
        phone=data.phone.strip(),
    )
    db.add(adoption)
    db.commit()
    db.refresh(adoption)
    return _adoption_to_out(adoption)


@router.patch("/{adoption_id}/status", response_model=schemas.AdoptionOut)
def update_adoption_status(
    adoption_id: str,
    data: schemas.AdoptionStatusUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    adoption = db.query(models.Adoption).filter(
        models.Adoption.id == adoption_id
    ).first()
    if not adoption:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if adoption.publisher_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tenés permiso para editar esta publicación")
    if data.status not in ("available", "reserved", "adopted"):
        raise HTTPException(status_code=400, detail="Estado inválido")

    adoption.status = data.status
    db.commit()
    db.refresh(adoption)
    return _adoption_to_out(adoption)


@router.delete("/{adoption_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_adoption(
    adoption_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    adoption = db.query(models.Adoption).filter(
        models.Adoption.id == adoption_id
    ).first()
    if not adoption:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if adoption.publisher_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tenés permiso para eliminar esta publicación")
    db.delete(adoption)
    db.commit()


@router.post("/{adoption_id}/contact")
def contact_adoption(
    adoption_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    adoption = db.query(models.Adoption).filter(
        models.Adoption.id == adoption_id
    ).first()
    if not adoption:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if adoption.status != models.AdoptionStatus.available:
        raise HTTPException(status_code=400, detail="Esta publicación ya no está disponible")

    # Create a conversation between interested user and publisher
    existing = db.query(models.Conversation).filter(
        ((models.Conversation.user1_id == current_user.id) &
         (models.Conversation.user2_id == adoption.publisher_id)) |
        ((models.Conversation.user1_id == adoption.publisher_id) &
         (models.Conversation.user2_id == current_user.id))
    ).first()

    if not existing:
        conv = models.Conversation(
            id=str(uuid.uuid4()),
            user1_id=current_user.id,
            user2_id=adoption.publisher_id,
        )
        db.add(conv)
        create_notification(
            db,
            user_id=adoption.publisher_id,
            type=TYPE_ADOPTION_INTEREST,
            title="Solicitud de adopcion",
            body=f"{current_user.name} quiere consultar por {adoption.name}.",
            image_url=(adoption.photos or [None])[0],
            action_id=conv.id,
        )
        db.commit()
        return {"conversation_id": conv.id}

    create_notification(
        db,
        user_id=adoption.publisher_id,
        type=TYPE_ADOPTION_INTEREST,
        title="Solicitud de adopcion",
        body=f"{current_user.name} quiere consultar por {adoption.name}.",
        image_url=(adoption.photos or [None])[0],
        action_id=existing.id,
    )
    db.commit()
    return {"conversation_id": existing.id}
