from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from . import models


@dataclass
class PatitasPack:
    id: str
    name: str
    price: int
    base_patitas: int
    bonus_patitas: int
    is_active: bool = True

    @property
    def total_patitas(self) -> int:
        return self.base_patitas + self.bonus_patitas


PATITAS_COSTS = {
    "lost_notification_2km": 50,
    "lost_notification_5km": 100,
    "lost_notification_10km": 200,
    "adoption_feature": 30,
    "adoption_feature_24h": 50,
    "matching_unlimited_likes_1d": 40,
    "matching_see_likes": 30,
    "matching_super_like": 10,
    "matching_advanced_filters_30d": 30,
    "profile_boost": 25,
    "profile_strong_boost": 60,
}


PATITAS_DESCRIPTIONS = {
    "lost_notification_2km": "Notificacion perdidos 2km",
    "lost_notification_5km": "Notificacion perdidos 5km",
    "lost_notification_10km": "Notificacion perdidos 10km",
    "adoption_feature": "Destacar adopcion",
    "adoption_feature_24h": "Destacar adopcion 24hs",
    "matching_unlimited_likes_1d": "Likes ilimitados 1 dia",
    "matching_see_likes": "Ver quien dio like",
    "matching_super_like": "Super Like enviado",
    "profile_boost": "Boost de perfil activado",
    "profile_strong_boost": "Boost fuerte activado",
}


def _row_to_pack(row: models.PatitasPackConfig) -> PatitasPack:
    return PatitasPack(
        id=row.id,
        name=row.name,
        price=row.price,
        base_patitas=row.base_patitas,
        bonus_patitas=row.bonus_patitas,
        is_active=row.is_active,
    )


def list_packs(db: Session, *, include_inactive: bool = False) -> list[PatitasPack]:
    query = db.query(models.PatitasPackConfig)
    if not include_inactive:
        query = query.filter(models.PatitasPackConfig.is_active == True)
    rows = query.order_by(models.PatitasPackConfig.price.asc()).all()
    return [_row_to_pack(row) for row in rows]


def get_pack(db: Session, pack_id: str) -> PatitasPack:
    row = (
        db.query(models.PatitasPackConfig)
        .filter(models.PatitasPackConfig.id == pack_id)
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pack de Patitas invalido",
        )
    if not row.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este pack de Patitas no esta disponible ahora",
        )
    return _row_to_pack(row)


def update_pack(
    db: Session,
    pack_id: str,
    *,
    name: Optional[str] = None,
    price: Optional[int] = None,
    base_patitas: Optional[int] = None,
    bonus_patitas: Optional[int] = None,
    is_active: Optional[bool] = None,
) -> PatitasPack:
    row = (
        db.query(models.PatitasPackConfig)
        .filter(models.PatitasPackConfig.id == pack_id)
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pack '{pack_id}' no encontrado",
        )

    if name is not None:
        row.name = name
    if price is not None:
        row.price = price
    if base_patitas is not None:
        row.base_patitas = base_patitas
    if bonus_patitas is not None:
        row.bonus_patitas = bonus_patitas
    if is_active is not None:
        row.is_active = is_active

    db.commit()
    db.refresh(row)
    return _row_to_pack(row)


def create_pending_purchase(
    db: Session,
    user: models.User,
    pack: PatitasPack,
    preference_id: str,
) -> models.PatitasTransaction:
    transaction = models.PatitasTransaction(
        usuario_id=user.id,
        tipo=models.PatitasTransactionType.compra,
        cantidad=pack.total_patitas,
        descripcion=f"Pack {pack.name} comprado",
        estado=models.PatitasTransactionStatus.pending,
        mercado_pago_preference_id=preference_id,
        pack_id=pack.id,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def approve_purchase_once(
    db: Session,
    payment_id: str,
    preference_id: Optional[str],
    pack_id: Optional[str],
    user_id: Optional[str],
) -> Optional[models.PatitasTransaction]:
    existing = (
        db.query(models.PatitasTransaction)
        .filter(models.PatitasTransaction.mercado_pago_payment_id == payment_id)
        .first()
    )
    if existing:
        return existing

    transaction = None
    if preference_id:
        transaction = (
            db.query(models.PatitasTransaction)
            .filter(
                models.PatitasTransaction.mercado_pago_preference_id == preference_id,
                models.PatitasTransaction.tipo == models.PatitasTransactionType.compra,
            )
            .first()
        )

    if transaction is None:
        if not pack_id or not user_id:
            return None
        pack = get_pack(db, pack_id)
        transaction = models.PatitasTransaction(
            usuario_id=user_id,
            tipo=models.PatitasTransactionType.compra,
            cantidad=pack.total_patitas,
            descripcion=f"Pack {pack.name} comprado",
            estado=models.PatitasTransactionStatus.pending,
            mercado_pago_preference_id=preference_id,
            pack_id=pack.id,
        )
        db.add(transaction)

    if transaction.estado == models.PatitasTransactionStatus.approved:
        return transaction

    user = db.query(models.User).filter(models.User.id == transaction.usuario_id).first()
    if not user:
        return None

    user.patitas = (user.patitas or 0) + transaction.cantidad
    transaction.estado = models.PatitasTransactionStatus.approved
    transaction.mercado_pago_payment_id = payment_id
    db.commit()
    db.refresh(transaction)
    return transaction


def consumir_patitas(
    db: Session,
    user: models.User,
    action: str,
    descripcion: Optional[str] = None,
) -> models.PatitasTransaction:
    cost = PATITAS_COSTS.get(action)
    if cost is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Accion de Patitas invalida",
        )

    if (user.patitas or 0) < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Saldo de Patitas insuficiente",
        )

    user.patitas = (user.patitas or 0) - cost
    transaction = models.PatitasTransaction(
        usuario_id=user.id,
        tipo=models.PatitasTransactionType.uso,
        cantidad=-cost,
        descripcion=descripcion or PATITAS_DESCRIPTIONS[action],
        estado=models.PatitasTransactionStatus.used,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction
