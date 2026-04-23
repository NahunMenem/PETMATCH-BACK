from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import (
    Adoption,
    Conversation,
    DeviceToken,
    LostPet,
    Match,
    Message,
    Notification,
    PatitasTransaction,
    Pet,
    PetLike,
    User,
)
from ..patitas_service import (
    list_packs as get_patitas_packs_config,
    update_pack as update_patitas_pack_config,
)

ADMIN_EMAIL = "nahundeveloper@gmail.com"

router = APIRouter(prefix="/admin", tags=["admin"])


def get_admin_user(current_user: User = Depends(get_current_user)):
    if current_user.email != ADMIN_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido al administrador",
        )
    return current_user


class PackUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    base_patitas: Optional[int] = None
    bonus_patitas: Optional[int] = None
    is_active: Optional[bool] = None


class AddPatitasRequest(BaseModel):
    amount: int
    reason: str = "Asignacion manual admin"


@router.get("/stats")
def get_stats(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_users = db.query(func.count(User.id)).scalar() or 0
    new_users_week = (
        db.query(func.count(User.id)).filter(User.created_at >= week_ago).scalar() or 0
    )
    prev_week_users = (
        db.query(func.count(User.id))
        .filter(
            User.created_at >= now - timedelta(days=14),
            User.created_at < week_ago,
        )
        .scalar()
        or 1
    )
    growth_pct = round(((new_users_week - prev_week_users) / prev_week_users) * 100, 1)

    total_pets = db.query(func.count(Pet.id)).scalar() or 0
    pets_active = db.query(func.count(Pet.id)).filter(Pet.is_active.is_(True)).scalar() or 0
    new_pets_week = (
        db.query(func.count(Pet.id)).filter(Pet.created_at >= week_ago).scalar() or 0
    )

    total_adoptions = db.query(func.count(Adoption.id)).scalar() or 0
    adoptions_available = (
        db.query(func.count(Adoption.id))
        .filter(Adoption.status == "available")
        .scalar()
        or 0
    )
    adoptions_reserved = (
        db.query(func.count(Adoption.id))
        .filter(Adoption.status == "reserved")
        .scalar()
        or 0
    )
    adoptions_adopted = (
        db.query(func.count(Adoption.id))
        .filter(Adoption.status == "adopted")
        .scalar()
        or 0
    )

    total_lost = db.query(func.count(LostPet.id)).scalar() or 0
    active_lost = (
        db.query(func.count(LostPet.id))
        .filter(LostPet.status == "active")
        .scalar()
        or 0
    )
    found_lost = (
        db.query(func.count(LostPet.id))
        .filter(LostPet.status == "found")
        .scalar()
        or 0
    )

    total_matches = db.query(func.count(Match.id)).scalar() or 0
    new_matches_week = (
        db.query(func.count(Match.id)).filter(Match.matched_at >= week_ago).scalar() or 0
    )

    total_transactions = (
        db.query(func.count(PatitasTransaction.id))
        .filter(
            PatitasTransaction.tipo == "compra",
            PatitasTransaction.estado == "approved",
        )
        .scalar()
        or 0
    )
    revenue_month = (
        db.query(func.sum(PatitasTransaction.cantidad))
        .filter(
            PatitasTransaction.tipo == "compra",
            PatitasTransaction.estado == "approved",
            PatitasTransaction.fecha >= month_ago,
        )
        .scalar()
        or 0
    )

    return {
        "users": {
            "total": total_users,
            "new_this_week": new_users_week,
            "growth_pct": growth_pct,
        },
        "pets": {
            "total": total_pets,
            "looking_for_partner": pets_active,
            "new_this_week": new_pets_week,
        },
        "adoptions": {
            "total": total_adoptions,
            "available": adoptions_available,
            "reserved": adoptions_reserved,
            "adopted": adoptions_adopted,
        },
        "lost_pets": {
            "total": total_lost,
            "active": active_lost,
            "found": found_lost,
        },
        "matches": {
            "total": total_matches,
            "new_this_week": new_matches_week,
        },
        "patitas": {
            "total_transactions": total_transactions,
            "revenue_this_month": int(revenue_month),
        },
    }


@router.get("/stats/growth")
def get_growth(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    result = []
    now = datetime.utcnow()

    for i in range(7, -1, -1):
        week_start = now - timedelta(weeks=i + 1)
        week_end = now - timedelta(weeks=i)
        label = week_end.strftime("%-d %b") if i > 0 else "Esta sem"
        users = (
            db.query(func.count(User.id))
            .filter(User.created_at >= week_start, User.created_at < week_end)
            .scalar()
            or 0
        )
        pets = (
            db.query(func.count(Pet.id))
            .filter(Pet.created_at >= week_start, Pet.created_at < week_end)
            .scalar()
            or 0
        )
        matches = (
            db.query(func.count(Match.id))
            .filter(Match.matched_at >= week_start, Match.matched_at < week_end)
            .scalar()
            or 0
        )
        result.append(
            {"label": label, "usuarios": users, "mascotas": pets, "matches": matches}
        )

    return result


@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    query = db.query(User)
    if search:
        query = query.filter(
            or_(User.email.ilike(f"%{search}%"), User.name.ilike(f"%{search}%"))
        )

    total = query.count()
    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    payload = []
    for user in users:
        payload.append(
            {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "photo_url": user.photo_url,
                "patitas": user.patitas,
                "created_at": user.created_at.isoformat(),
                "pets_count": db.query(func.count(Pet.id)).filter(Pet.owner_id == user.id).scalar()
                or 0,
                "lost_reports_count": db.query(func.count(LostPet.id))
                .filter(LostPet.reporter_id == user.id)
                .scalar()
                or 0,
                "adoptions_count": db.query(func.count(Adoption.id))
                .filter(Adoption.publisher_id == user.id)
                .scalar()
                or 0,
            }
        )

    return {"total": total, "page": page, "users": payload}


@router.post("/users/{user_id}/patitas")
def add_patitas(
    user_id: str,
    body: AddPatitasRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.patitas += body.amount
    tx = PatitasTransaction(
        usuario_id=user_id,
        tipo="compra",
        cantidad=body.amount,
        descripcion=f"Admin: {body.reason}",
        estado="approved",
    )
    db.add(tx)
    db.commit()
    db.refresh(user)

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "photo_url": user.photo_url,
        "patitas": user.patitas,
        "created_at": user.created_at.isoformat(),
        "pets_count": db.query(func.count(Pet.id)).filter(Pet.owner_id == user.id).scalar()
        or 0,
        "lost_reports_count": db.query(func.count(LostPet.id))
        .filter(LostPet.reporter_id == user.id)
        .scalar()
        or 0,
        "adoptions_count": db.query(func.count(Adoption.id))
        .filter(Adoption.publisher_id == user.id)
        .scalar()
        or 0,
    }


@router.delete("/users/{user_id}")
def delete_user_cascade(
    user_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    pet_ids = [pet_id for (pet_id,) in db.query(Pet.id).filter(Pet.owner_id == user_id).all()]
    conversation_ids = [
        conversation_id
        for (conversation_id,) in db.query(Conversation.id)
        .filter(or_(Conversation.user1_id == user_id, Conversation.user2_id == user_id))
        .all()
    ]

    if pet_ids:
        db.query(PetLike).filter(
            or_(PetLike.liker_pet_id.in_(pet_ids), PetLike.liked_pet_id.in_(pet_ids))
        ).delete(synchronize_session=False)
        db.query(Match).filter(
            or_(Match.pet1_id.in_(pet_ids), Match.pet2_id.in_(pet_ids))
        ).delete(synchronize_session=False)
        db.query(LostPet).filter(LostPet.pet_id.in_(pet_ids)).delete(
            synchronize_session=False
        )

    if conversation_ids:
        db.query(Message).filter(Message.conversation_id.in_(conversation_ids)).delete(
            synchronize_session=False
        )
        db.query(Match).filter(Match.conversation_id.in_(conversation_ids)).delete(
            synchronize_session=False
        )
        db.query(Conversation).filter(Conversation.id.in_(conversation_ids)).delete(
            synchronize_session=False
        )

    db.query(LostPet).filter(LostPet.reporter_id == user_id).delete(
        synchronize_session=False
    )
    db.query(Adoption).filter(Adoption.publisher_id == user_id).delete(
        synchronize_session=False
    )
    db.query(Notification).filter(Notification.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(DeviceToken).filter(DeviceToken.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(PatitasTransaction).filter(PatitasTransaction.usuario_id == user_id).delete(
        synchronize_session=False
    )
    db.query(Pet).filter(Pet.owner_id == user_id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()

    return {"success": True, "deleted_user_id": user_id}


@router.get("/patitas/packs")
def list_packs(
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    return [
        {
            "id": pack.id,
            "name": pack.name,
            "price": pack.price,
            "base_patitas": pack.base_patitas,
            "bonus_patitas": pack.bonus_patitas,
            "is_active": pack.is_active,
        }
        for pack in get_patitas_packs_config(db, include_inactive=True)
    ]


@router.put("/patitas/packs/{pack_id}")
def update_pack(
    pack_id: str,
    body: PackUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    pack = update_patitas_pack_config(
        db,
        pack_id,
        name=body.name,
        price=body.price,
        base_patitas=body.base_patitas,
        bonus_patitas=body.bonus_patitas,
        is_active=body.is_active,
    )
    return {
        "id": pack.id,
        "name": pack.name,
        "price": pack.price,
        "base_patitas": pack.base_patitas,
        "bonus_patitas": pack.bonus_patitas,
        "is_active": pack.is_active,
    }
