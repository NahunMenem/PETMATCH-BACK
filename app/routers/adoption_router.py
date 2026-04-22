import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..auth import get_current_user

router = APIRouter(prefix="/adoptions", tags=["adoptions"])


def _adoption_to_out(adoption: models.Adoption) -> schemas.AdoptionOut:
    pub = adoption.publisher
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
        status=adoption.status.value,
        published_at=adoption.published_at,
    )


@router.get("", response_model=List[schemas.AdoptionOut])
def get_adoptions(
    type: Optional[str] = Query(None),
    max_distance: Optional[int] = Query(None),
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
    return [_adoption_to_out(a) for a in adoptions]


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
    return [_adoption_to_out(a) for a in adoptions]


@router.post("", response_model=schemas.AdoptionOut, status_code=status.HTTP_201_CREATED)
def create_adoption(
    data: schemas.AdoptionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
        db.commit()
        return {"conversation_id": conv.id}

    return {"conversation_id": existing.id}
