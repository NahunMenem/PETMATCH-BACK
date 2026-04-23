"""
PawMatch Admin Router — v3
Copiar a: app/routers/admin_router.py
Ver INSTALL.md para registrarlo en main.py
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import User, Pet, Adoption, LostPet, Match, PatitasTransaction

ADMIN_EMAIL = "nahundeveloper@gmail.com"

router = APIRouter(prefix="/admin", tags=["admin"])


# ─── Auth dependency ──────────────────────────────────────────────────────────

def get_admin_user(current_user: User = Depends(get_current_user)):
    if current_user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Acceso restringido al administrador")
    return current_user


# ─── Schemas ──────────────────────────────────────────────────────────────────

class PackUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    base_patitas: Optional[int] = None
    bonus_patitas: Optional[int] = None
    is_active: Optional[bool] = None


class AddPatitasRequest(BaseModel):
    amount: int
    reason: str = "Asignación manual admin"


# Pack store in-memory
_PACKS: dict = {
    "starter": {"id": "starter", "name": "Starter", "price": 3000,  "base_patitas": 100, "bonus_patitas": 0,   "is_active": True},
    "popular": {"id": "popular", "name": "Popular", "price": 6000,  "base_patitas": 250, "bonus_patitas": 25,  "is_active": True},
    "pro":     {"id": "pro",     "name": "Pro",     "price": 10000, "base_patitas": 500, "bonus_patitas": 100, "is_active": True},
}


# ─── Stats ────────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    now = datetime.utcnow()
    week_ago  = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_users     = db.query(func.count(User.id)).scalar() or 0
    new_users_week  = db.query(func.count(User.id)).filter(User.created_at >= week_ago).scalar() or 0
    prev_week_users = db.query(func.count(User.id)).filter(
        User.created_at >= now - timedelta(days=14), User.created_at < week_ago
    ).scalar() or 1
    growth_pct = round(((new_users_week - prev_week_users) / prev_week_users) * 100, 1)

    total_pets  = db.query(func.count(Pet.id)).scalar() or 0
    pets_active = db.query(func.count(Pet.id)).filter(Pet.is_active == True).scalar() or 0
    new_pets_wk = db.query(func.count(Pet.id)).filter(Pet.created_at >= week_ago).scalar() or 0

    total_adoptions = db.query(func.count(Adoption.id)).scalar() or 0
    avail    = db.query(func.count(Adoption.id)).filter(Adoption.status == "available").scalar() or 0
    reserved = db.query(func.count(Adoption.id)).filter(Adoption.status == "reserved").scalar() or 0
    adopted  = db.query(func.count(Adoption.id)).filter(Adoption.status == "adopted").scalar() or 0

    total_lost  = db.query(func.count(LostPet.id)).scalar() or 0
    active_lost = db.query(func.count(LostPet.id)).filter(LostPet.status == "active").scalar() or 0
    found       = db.query(func.count(LostPet.id)).filter(LostPet.status == "found").scalar() or 0

    total_matches  = db.query(func.count(Match.id)).scalar() or 0
    new_matches_wk = db.query(func.count(Match.id)).filter(Match.matched_at >= week_ago).scalar() or 0

    total_tx = db.query(func.count(PatitasTransaction.id)).filter(
        PatitasTransaction.tipo == "compra", PatitasTransaction.estado == "approved"
    ).scalar() or 0
    revenue_month = db.query(func.sum(PatitasTransaction.cantidad)).filter(
        PatitasTransaction.tipo == "compra",
        PatitasTransaction.estado == "approved",
        PatitasTransaction.fecha >= month_ago,
    ).scalar() or 0

    return {
        "users":     {"total": total_users,     "new_this_week": new_users_week,  "growth_pct": growth_pct},
        "pets":      {"total": total_pets,       "looking_for_partner": pets_active, "new_this_week": new_pets_wk},
        "adoptions": {"total": total_adoptions,  "available": avail, "reserved": reserved, "adopted": adopted},
        "lost_pets": {"total": total_lost,       "active": active_lost, "found": found},
        "matches":   {"total": total_matches,    "new_this_week": new_matches_wk},
        "patitas":   {"total_transactions": total_tx, "revenue_this_month": int(revenue_month)},
    }


@router.get("/stats/growth")
def get_growth(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    result = []
    now = datetime.utcnow()
    for i in range(7, -1, -1):
        w_start = now - timedelta(weeks=i + 1)
        w_end   = now - timedelta(weeks=i)
        label   = w_end.strftime("%-d %b") if i > 0 else "Esta sem"
        users   = db.query(func.count(User.id)).filter(User.created_at  >= w_start, User.created_at  < w_end).scalar() or 0
        pets    = db.query(func.count(Pet.id)).filter(Pet.created_at    >= w_start, Pet.created_at   < w_end).scalar() or 0
        matches = db.query(func.count(Match.id)).filter(Match.matched_at >= w_start, Match.matched_at < w_end).scalar() or 0
        result.append({"label": label, "usuarios": users, "mascotas": pets, "matches": matches})
    return result


# ─── Users ────────────────────────────────────────────────────────────────────

@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    q = db.query(User)
    if search:
        q = q.filter(or_(User.email.ilike(f"%{search}%"), User.name.ilike(f"%{search}%")))
    total = q.count()
    users = q.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return {
        "total": total,
        "page": page,
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.name,
                "photo_url": u.photo_url,
                "patitas": u.patitas,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
    }


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
    }


# ─── Patitas packs ────────────────────────────────────────────────────────────

@router.get("/patitas/packs")
def list_packs(_: User = Depends(get_admin_user)):
    return list(_PACKS.values())


@router.put("/patitas/packs/{pack_id}")
def update_pack(pack_id: str, body: PackUpdate, _: User = Depends(get_admin_user)):
    if pack_id not in _PACKS:
        raise HTTPException(status_code=404, detail=f"Pack '{pack_id}' no encontrado")
    _PACKS[pack_id].update(body.model_dump(exclude_none=True))
    return _PACKS[pack_id]
