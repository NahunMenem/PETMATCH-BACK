from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from . import models


@dataclass(frozen=True)
class PatitasPack:
    id: str
    name: str
    price: int
    base_patitas: int
    bonus_patitas: int

    @property
    def total_patitas(self) -> int:
        return self.base_patitas + self.bonus_patitas


PATITAS_PACKS = {
    "starter": PatitasPack("starter", "Starter", 3000, 100, 0),
    "popular": PatitasPack("popular", "Popular", 6000, 250, 25),
    "pro": PatitasPack("pro", "Pro", 10000, 500, 100),
}


PATITAS_COSTS = {
    "lost_notification_2km": 30,
    "lost_notification_5km": 50,
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
    "lost_notification_2km": "Notificación perdidos 2km",
    "lost_notification_5km": "Notificación perdidos 5km",
    "adoption_feature": "Destacar adopción",
    "adoption_feature_24h": "Destacar adopción 24hs",
    "matching_unlimited_likes_1d": "Likes ilimitados 1 día",
    "matching_see_likes": "Ver quién dio like",
    "matching_super_like": "Super Like enviado",
    "profile_boost": "Boost de perfil activado",
    "profile_strong_boost": "Boost fuerte activado",
}


def get_pack(pack_id: str) -> PatitasPack:
    pack = PATITAS_PACKS.get(pack_id)
    if not pack:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pack de Patitas inválido",
        )
    return pack


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
        pack = get_pack(pack_id)
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
            detail="Acción de Patitas inválida",
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

