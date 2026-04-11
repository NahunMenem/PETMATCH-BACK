import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, not_, exists

from ..database import get_db
from .. import models, schemas
from ..auth import get_current_user

router = APIRouter(prefix="/pets", tags=["pets"])


def _pet_to_out(pet: models.Pet, distance_km: Optional[float] = None) -> schemas.PetOut:
    owner = pet.owner
    return schemas.PetOut(
        id=pet.id,
        owner_id=pet.owner_id,
        owner_name=owner.name,
        owner_photo_url=owner.photo_url,
        owner_verified=owner.is_verified,
        name=pet.name,
        type=pet.type.value,
        breed=pet.breed,
        age=pet.age,
        sex=pet.sex.value,
        size=pet.size.value,
        vaccines_up_to_date=pet.vaccines_up_to_date,
        sterilized=pet.sterilized,
        photos=pet.photos or [],
        description=pet.description,
        distance_km=distance_km,
        is_active=pet.is_active,
        created_at=pet.created_at,
    )


@router.get("/mine", response_model=List[schemas.PetOut])
def get_my_pets(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pets = db.query(models.Pet).filter(models.Pet.owner_id == current_user.id).all()
    return [_pet_to_out(p) for p in pets]


@router.get("/explore", response_model=List[schemas.PetOut])
def explore_pets(
    type: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    page: int = Query(1, ge=1),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Get current user's pet IDs to exclude
    my_pet_ids = [
        p.id for p in db.query(models.Pet.id)
        .filter(models.Pet.owner_id == current_user.id).all()
    ]

    # Already liked/disliked pets
    interacted_pet_ids = [
        l.liked_pet_id for l in db.query(models.PetLike.liked_pet_id)
        .filter(models.PetLike.liker_pet_id.in_(my_pet_ids)).all()
    ] if my_pet_ids else []

    excluded = set(my_pet_ids + interacted_pet_ids)

    query = db.query(models.Pet).filter(
        models.Pet.is_active == True,
        models.Pet.owner_id != current_user.id,
    )

    if excluded:
        query = query.filter(~models.Pet.id.in_(excluded))

    if type in ("dog", "cat"):
        query = query.filter(models.Pet.type == type)

    pets = query.offset((page - 1) * 20).limit(20).all()
    return [_pet_to_out(p) for p in pets]


@router.post("", response_model=schemas.PetOut, status_code=status.HTTP_201_CREATED)
def create_pet(
    data: schemas.PetCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pet = models.Pet(
        id=str(uuid.uuid4()),
        owner_id=current_user.id,
        name=data.name,
        type=data.type,
        breed=data.breed,
        age=data.age,
        sex=data.sex,
        size=data.size,
        vaccines_up_to_date=data.vaccines_up_to_date,
        sterilized=data.sterilized,
        photos=data.photos,
        description=data.description,
    )
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return _pet_to_out(pet)


@router.put("/{pet_id}", response_model=schemas.PetOut)
def update_pet(
    pet_id: str,
    data: schemas.PetUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pet = db.query(models.Pet).filter(
        models.Pet.id == pet_id,
        models.Pet.owner_id == current_user.id,
    ).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(pet, field, value)
    db.commit()
    db.refresh(pet)
    return _pet_to_out(pet)


@router.post("/like")
def like_pet(
    data: schemas.SwipeAction,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Get user's first active pet as the liker
    my_pet = db.query(models.Pet).filter(
        models.Pet.owner_id == current_user.id,
        models.Pet.is_active == True,
    ).first()
    if not my_pet:
        raise HTTPException(status_code=400, detail="No tenés mascota activa")

    liked_pet = db.query(models.Pet).filter(models.Pet.id == data.pet_id).first()
    if not liked_pet:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")

    # Save like
    like = models.PetLike(
        id=str(uuid.uuid4()),
        liker_pet_id=my_pet.id,
        liked_pet_id=liked_pet.id,
        is_dislike=False,
    )
    db.add(like)
    db.flush()

    # Check for mutual like (match)
    mutual = db.query(models.PetLike).filter(
        models.PetLike.liker_pet_id == liked_pet.id,
        models.PetLike.liked_pet_id == my_pet.id,
        models.PetLike.is_dislike == False,
    ).first()

    if mutual:
        # Create conversation
        conv = models.Conversation(
            id=str(uuid.uuid4()),
            user1_id=current_user.id,
            user2_id=liked_pet.owner_id,
        )
        db.add(conv)
        db.flush()

        # Create match
        match = models.Match(
            id=str(uuid.uuid4()),
            pet1_id=my_pet.id,
            pet2_id=liked_pet.id,
            conversation_id=conv.id,
        )
        db.add(match)
        db.commit()
        return {"match": True, "match_id": match.id, "conversation_id": conv.id}

    db.commit()
    return {"match": False}


@router.post("/dislike")
def dislike_pet(
    data: schemas.SwipeAction,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    my_pet = db.query(models.Pet).filter(
        models.Pet.owner_id == current_user.id,
        models.Pet.is_active == True,
    ).first()
    if not my_pet:
        raise HTTPException(status_code=400, detail="No tenés mascota activa")

    dislike = models.PetLike(
        id=str(uuid.uuid4()),
        liker_pet_id=my_pet.id,
        liked_pet_id=data.pet_id,
        is_dislike=True,
    )
    db.add(dislike)
    db.commit()
    return {"ok": True}
