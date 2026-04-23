import uuid
import math
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, not_, exists

from ..database import get_db
from .. import models, schemas
from ..auth import get_current_user
from ..notification_service import (
    TYPE_LIKE,
    TYPE_NEW_MATCH,
    create_notification,
)
from ..patitas_service import PATITAS_DESCRIPTIONS, consumir_patitas

router = APIRouter(prefix="/pets", tags=["pets"])

SEE_LIKES_ACTION = "matching_see_likes"
SUPER_LIKE_ACTION = "matching_super_like"
ADVANCED_FILTERS_DESCRIPTION = "Filtros avanzados 30 dias"
FREE_EXPLORE_DISTANCE_KM = 10


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


def _likes_unlocked(db: Session, user: models.User) -> bool:
    since = datetime.utcnow() - timedelta(days=30)
    descriptions = {
        PATITAS_DESCRIPTIONS[SEE_LIKES_ACTION],
        "Ver quien dio like",
        "Ver quién dio like",
        "Ver quiÃ©n dio like",
    }
    return (
        db.query(models.PatitasTransaction.id)
        .filter(
            models.PatitasTransaction.usuario_id == user.id,
            models.PatitasTransaction.tipo == models.PatitasTransactionType.uso,
            models.PatitasTransaction.estado == models.PatitasTransactionStatus.used,
            models.PatitasTransaction.descripcion.in_(descriptions),
            models.PatitasTransaction.fecha >= since,
        )
        .first()
        is not None
    )


def _advanced_filters_unlocked(db: Session, user: models.User) -> bool:
    since = datetime.utcnow() - timedelta(days=30)
    return (
        db.query(models.PatitasTransaction.id)
        .filter(
            models.PatitasTransaction.usuario_id == user.id,
            models.PatitasTransaction.tipo == models.PatitasTransactionType.uso,
            models.PatitasTransaction.estado == models.PatitasTransactionStatus.used,
            models.PatitasTransaction.descripcion == ADVANCED_FILTERS_DESCRIPTION,
            models.PatitasTransaction.fecha >= since,
        )
        .first()
        is not None
    )


def _received_likes_response(
    db: Session,
    user: models.User,
    unlocked: bool,
) -> schemas.ReceivedLikesOut:
    my_pet_ids = [
        pet_id
        for (pet_id,) in db.query(models.Pet.id)
        .filter(models.Pet.owner_id == user.id)
        .all()
    ]
    if not my_pet_ids:
        return schemas.ReceivedLikesOut(total=0, unlocked=unlocked, likes=[])

    query = (
        db.query(models.PetLike)
        .join(models.Pet, models.Pet.id == models.PetLike.liker_pet_id)
        .filter(
            models.PetLike.liked_pet_id.in_(my_pet_ids),
            models.PetLike.is_dislike == False,
            models.Pet.owner_id != user.id,
            models.Pet.is_active == True,
        )
        .order_by(models.PetLike.id.desc())
    )
    likes = query.all()

    items = []
    for like in likes:
        liker_pet = like.liker_pet
        liked_pet = like.liked_pet
        photo = (liker_pet.photos or [None])[0]
        response_sent = (
            db.query(models.PetLike.id)
            .filter(
                models.PetLike.liker_pet_id.in_(my_pet_ids),
                models.PetLike.liked_pet_id == liker_pet.id,
            )
            .first()
            is not None
        )
        if unlocked:
            items.append(
                schemas.ReceivedLikeOut(
                    pet_id=liker_pet.id,
                    pet_name=liker_pet.name,
                    pet_photo=photo,
                    pet_type=liker_pet.type.value,
                    breed=liker_pet.breed,
                    age=liker_pet.age,
                    sex=liker_pet.sex.value,
                    size=liker_pet.size.value,
                    vaccines_up_to_date=liker_pet.vaccines_up_to_date,
                    sterilized=liker_pet.sterilized,
                    photos=liker_pet.photos or [],
                    description=liker_pet.description,
                    response_sent=response_sent,
                    owner_name=liker_pet.owner.name,
                    liked_my_pet_id=liked_pet.id,
                    liked_my_pet_name=liked_pet.name,
                )
            )
        else:
            items.append(schemas.ReceivedLikeOut(pet_photo=photo))

    return schemas.ReceivedLikesOut(
        total=len(likes),
        unlocked=unlocked,
        likes=items[:20] if unlocked else items[:4],
    )


def _create_like(
    *,
    data: schemas.SwipeAction,
    current_user: models.User,
    db: Session,
    is_super_like: bool = False,
):
    my_pet = db.query(models.Pet).filter(
        models.Pet.owner_id == current_user.id,
        models.Pet.is_active == True,
    ).first()
    if not my_pet:
        raise HTTPException(status_code=400, detail="No tenes mascota activa")

    liked_pet = db.query(models.Pet).filter(
        models.Pet.id == data.pet_id,
        models.Pet.is_active == True,
    ).first()
    if not liked_pet:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")

    if liked_pet.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="No podes likear tu mascota")

    existing = db.query(models.PetLike).filter(
        models.PetLike.liker_pet_id == my_pet.id,
        models.PetLike.liked_pet_id == liked_pet.id,
    ).first()
    if existing:
        existing.is_dislike = False
        existing.is_super_like = existing.is_super_like or is_super_like
    else:
        like = models.PetLike(
            id=str(uuid.uuid4()),
            liker_pet_id=my_pet.id,
            liked_pet_id=liked_pet.id,
            is_dislike=False,
            is_super_like=is_super_like,
        )
        db.add(like)
    db.flush()

    create_notification(
        db,
        user_id=liked_pet.owner_id,
        type=TYPE_LIKE,
        title="Super Like recibido" if is_super_like else "Nuevo like",
        body=(
            f"A {my_pet.name} le encanto {liked_pet.name}."
            if is_super_like
            else f"A {my_pet.name} le gusto {liked_pet.name}."
        ),
        image_url=(my_pet.photos or [None])[0],
        action_id=my_pet.id,
    )

    mutual = db.query(models.PetLike).filter(
        models.PetLike.liker_pet_id == liked_pet.id,
        models.PetLike.liked_pet_id == my_pet.id,
        models.PetLike.is_dislike == False,
    ).first()

    if mutual:
        existing_conversation = (
            db.query(models.Conversation)
            .filter(
                (
                    (models.Conversation.user1_id == current_user.id)
                    & (models.Conversation.user2_id == liked_pet.owner_id)
                )
                | (
                    (models.Conversation.user1_id == liked_pet.owner_id)
                    & (models.Conversation.user2_id == current_user.id)
                )
            )
            .first()
        )
        conv = existing_conversation or models.Conversation(
            id=str(uuid.uuid4()),
            user1_id=current_user.id,
            user2_id=liked_pet.owner_id,
        )
        if not existing_conversation:
            db.add(conv)
            db.flush()

        match = models.Match(
            id=str(uuid.uuid4()),
            pet1_id=my_pet.id,
            pet2_id=liked_pet.id,
            conversation_id=conv.id,
        )
        db.add(match)
        create_notification(
            db,
            user_id=current_user.id,
            type=TYPE_NEW_MATCH,
            title="Nuevo match",
            body=f"{my_pet.name} y {liked_pet.name} hicieron match.",
            image_url=(liked_pet.photos or [None])[0],
            action_id=conv.id,
        )
        create_notification(
            db,
            user_id=liked_pet.owner_id,
            type=TYPE_NEW_MATCH,
            title="Nuevo match",
            body=f"{liked_pet.name} y {my_pet.name} hicieron match.",
            image_url=(my_pet.photos or [None])[0],
            action_id=conv.id,
        )
        db.commit()
        return {"match": True, "match_id": match.id, "conversation_id": conv.id}

    db.commit()
    return {"match": False}


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
    breed: Optional[str] = Query(None),
    vaccinated: Optional[bool] = Query(None),
    sterilized: Optional[bool] = Query(None),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    max_distance: int = Query(10, ge=1, le=500),
    page: int = Query(1, ge=1),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    advanced_filters_active = _advanced_filters_unlocked(db, current_user)
    effective_max_distance = (
        max_distance if advanced_filters_active else min(max_distance, FREE_EXPLORE_DISTANCE_KM)
    )

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
    if breed:
        query = query.filter(models.Pet.breed.ilike(f"%{breed.strip()}%"))
    if vaccinated is True:
        query = query.filter(models.Pet.vaccines_up_to_date == True)
    if sterilized is True:
        query = query.filter(models.Pet.sterilized == True)

    user_lat = lat if lat is not None else current_user.latitude
    user_lng = lng if lng is not None else current_user.longitude

    candidates = query.all()
    items = []
    for pet in candidates:
        distance = _distance_km(user_lat, user_lng, pet.owner.latitude, pet.owner.longitude)
        if user_lat is not None and user_lng is not None:
            if distance is None or distance > effective_max_distance:
                continue
        items.append((distance if distance is not None else 999999.0, pet, distance))

    items.sort(key=lambda item: item[0])
    page_items = items[(page - 1) * 20 : page * 20]
    return [_pet_to_out(pet, distance_km=distance) for _, pet, distance in page_items]


@router.get("/likes-received", response_model=schemas.ReceivedLikesOut)
def get_likes_received(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _received_likes_response(
        db=db,
        user=current_user,
        unlocked=_likes_unlocked(db, current_user),
    )


@router.post("/likes-received/unlock", response_model=schemas.ReceivedLikesOut)
def unlock_likes_received(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _likes_unlocked(db, current_user):
        consumir_patitas(
            db,
            current_user,
            SEE_LIKES_ACTION,
            descripcion=PATITAS_DESCRIPTIONS[SEE_LIKES_ACTION],
        )
    return _received_likes_response(db=db, user=current_user, unlocked=True)


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
    return _create_like(data=data, current_user=current_user, db=db)


@router.post("/super-like")
def super_like_pet(
    data: schemas.SwipeAction,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not db.query(models.Pet.id).filter(
        models.Pet.owner_id == current_user.id,
        models.Pet.is_active == True,
    ).first():
        raise HTTPException(status_code=400, detail="No tenes mascota activa")
    target_pet = db.query(models.Pet).filter(
        models.Pet.id == data.pet_id,
        models.Pet.is_active == True,
    ).first()
    if not target_pet:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    if target_pet.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="No podes likear tu mascota")
    consumir_patitas(
        db,
        current_user,
        SUPER_LIKE_ACTION,
        descripcion=PATITAS_DESCRIPTIONS[SUPER_LIKE_ACTION],
    )
    return _create_like(
        data=data,
        current_user=current_user,
        db=db,
        is_super_like=True,
    )


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

    liked_pet = db.query(models.Pet).filter(
        models.Pet.id == data.pet_id,
        models.Pet.is_active == True,
    ).first()
    if not liked_pet:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    if liked_pet.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="No podes descartar tu mascota")

    existing = db.query(models.PetLike).filter(
        models.PetLike.liker_pet_id == my_pet.id,
        models.PetLike.liked_pet_id == liked_pet.id,
    ).first()
    if existing:
        existing.is_dislike = True
        existing.is_super_like = False
    else:
        dislike = models.PetLike(
            id=str(uuid.uuid4()),
            liker_pet_id=my_pet.id,
            liked_pet_id=liked_pet.id,
            is_dislike=True,
        )
        db.add(dislike)
    db.commit()
    return {"ok": True}
