import hmac
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..patitas_service import (
    PATITAS_PACKS,
    approve_purchase_once,
    consumir_patitas,
    create_pending_purchase,
    get_pack,
)

router = APIRouter(tags=["patitas"])

ADVANCED_FILTERS_ACTION = "matching_advanced_filters_30d"
ADVANCED_FILTERS_DESCRIPTION = "Filtros avanzados 30 dias"


def _advanced_filters_expires_at(db: Session, user_id: str):
    since = datetime.utcnow() - timedelta(days=30)
    transaction = (
        db.query(models.PatitasTransaction)
        .filter(
            models.PatitasTransaction.usuario_id == user_id,
            models.PatitasTransaction.tipo == models.PatitasTransactionType.uso,
            models.PatitasTransaction.estado == models.PatitasTransactionStatus.used,
            models.PatitasTransaction.descripcion == ADVANCED_FILTERS_DESCRIPTION,
            models.PatitasTransaction.fecha >= since,
        )
        .order_by(models.PatitasTransaction.fecha.desc())
        .first()
    )
    if not transaction:
        return None
    return transaction.fecha + timedelta(days=30)


def _pack_out(pack):
    return schemas.PatitasPackOut(
        id=pack.id,
        name=pack.name,
        price=pack.price,
        base_patitas=pack.base_patitas,
        bonus_patitas=pack.bonus_patitas,
        total_patitas=pack.total_patitas,
    )


def _require_mp_token() -> str:
    if not settings.MERCADO_PAGO_ACCESS_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mercado Pago no está configurado",
        )
    return settings.MERCADO_PAGO_ACCESS_TOKEN


def _parse_signature(signature: str) -> dict[str, str]:
    parts = {}
    for item in signature.split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            parts[key.strip()] = value.strip()
    return parts


def _validate_webhook_secret(
    x_webhook_secret: Optional[str],
    x_signature: Optional[str],
    x_request_id: Optional[str],
    data_id: Optional[str],
) -> None:
    expected = settings.MERCADO_PAGO_WEBHOOK_SECRET
    if not expected:
        return

    if hmac.compare_digest(x_webhook_secret or "", expected):
        return

    if x_signature and x_request_id and data_id:
        signature = _parse_signature(x_signature)
        ts = signature.get("ts")
        v1 = signature.get("v1")
        if ts and v1:
            manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
            digest = hmac.new(
                expected.encode(),
                manifest.encode(),
                "sha256",
            ).hexdigest()
            if hmac.compare_digest(digest, v1):
                return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Webhook no autorizado",
    )


def _fetch_mp_payment(payment_id: str, token: str) -> dict[str, Any]:
    response = requests.get(
        f"https://api.mercadopago.com/v1/payments/{payment_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=12,
    )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo validar el pago en Mercado Pago",
        )
    return response.json()


@router.get("/patitas/packs", response_model=list[schemas.PatitasPackOut])
def list_packs():
    return [_pack_out(pack) for pack in PATITAS_PACKS.values()]


@router.get("/patitas/wallet", response_model=schemas.PatitasWalletOut)
def wallet(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    transactions = (
        db.query(models.PatitasTransaction)
        .filter(models.PatitasTransaction.usuario_id == current_user.id)
        .order_by(models.PatitasTransaction.fecha.desc())
        .limit(50)
        .all()
    )
    return schemas.PatitasWalletOut(
        patitas=current_user.patitas or 0,
        transactions=transactions,
    )


@router.post("/patitas/consumir", response_model=schemas.ConsumirPatitasOut)
def consumir(
    data: schemas.ConsumirPatitasRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    transaction = consumir_patitas(
        db,
        current_user,
        data.action,
        descripcion=data.descripcion,
    )
    db.refresh(current_user)
    return schemas.ConsumirPatitasOut(
        patitas=current_user.patitas or 0,
        transaction=transaction,
    )


@router.get("/patitas/advanced-filters")
def advanced_filters_status(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expires_at = _advanced_filters_expires_at(db, current_user.id)
    return {
        "active": expires_at is not None and expires_at > datetime.utcnow(),
        "expires_at": expires_at,
        "cost": 30,
    }


@router.post("/patitas/advanced-filters/activate")
def activate_advanced_filters(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expires_at = _advanced_filters_expires_at(db, current_user.id)
    if expires_at is None or expires_at <= datetime.utcnow():
        consumir_patitas(
            db,
            current_user,
            ADVANCED_FILTERS_ACTION,
            descripcion=ADVANCED_FILTERS_DESCRIPTION,
        )
        db.refresh(current_user)
        expires_at = _advanced_filters_expires_at(db, current_user.id)
    return {
        "active": True,
        "expires_at": expires_at,
        "cost": 30,
        "patitas": current_user.patitas or 0,
    }


@router.post("/crear-preferencia", response_model=schemas.PreferenciaPatitasOut)
def crear_preferencia(
    data: schemas.CrearPreferenciaPatitas,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = _require_mp_token()
    pack = get_pack(data.pack_id)
    payload = {
        "items": [
            {
                "title": f"PetMatch - Pack {pack.name}",
                "quantity": 1,
                "currency_id": "ARS",
                "unit_price": pack.price,
            }
        ],
        "external_reference": f"{current_user.id}:{pack.id}",
        "metadata": {
            "user_id": current_user.id,
            "pack_id": pack.id,
            "patitas": pack.total_patitas,
        },
        "back_urls": {
            "success": settings.MERCADO_PAGO_BACK_URL_SUCCESS,
            "failure": settings.MERCADO_PAGO_BACK_URL_FAILURE,
            "pending": settings.MERCADO_PAGO_BACK_URL_PENDING,
        },
        "notification_url": settings.MERCADO_PAGO_NOTIFICATION_URL,
        "auto_return": "approved",
    }
    response = requests.post(
        "https://api.mercadopago.com/checkout/preferences",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=12,
    )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo crear la preferencia de Mercado Pago",
        )

    preference = response.json()
    preference_id = preference["id"]
    create_pending_purchase(db, current_user, pack, preference_id)
    return schemas.PreferenciaPatitasOut(
        preference_id=preference_id,
        init_point=preference["init_point"],
        sandbox_init_point=preference.get("sandbox_init_point"),
    )


@router.post("/webhook-mercadopago")
async def webhook_mercadopago(
    request: Request,
    x_webhook_secret: Optional[str] = Header(default=None),
    x_signature: Optional[str] = Header(default=None),
    x_request_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    payload = await request.json()
    event_type = payload.get("type") or payload.get("topic")
    data = payload.get("data") or {}
    payment_id = data.get("id") or payload.get("id")
    _validate_webhook_secret(
        x_webhook_secret=x_webhook_secret,
        x_signature=x_signature,
        x_request_id=x_request_id,
        data_id=str(payment_id) if payment_id else None,
    )
    token = _require_mp_token()
    if event_type not in {"payment", "merchant_order"} or not payment_id:
        return {"ok": True}

    payment = _fetch_mp_payment(str(payment_id), token)
    if payment.get("status") != "approved":
        return {"ok": True, "status": payment.get("status")}

    metadata = payment.get("metadata") or {}
    preference_id = payment.get("preference_id")
    user_id = metadata.get("user_id")
    pack_id = metadata.get("pack_id")

    external_reference = payment.get("external_reference")
    if external_reference and (not user_id or not pack_id):
        parts = external_reference.split(":", 1)
        if len(parts) == 2:
            user_id = user_id or parts[0]
            pack_id = pack_id or parts[1]

    transaction = approve_purchase_once(
        db=db,
        payment_id=str(payment_id),
        preference_id=preference_id,
        pack_id=pack_id,
        user_id=user_id,
    )
    return {"ok": True, "transaction_id": transaction.id if transaction else None}
