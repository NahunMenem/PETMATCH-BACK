from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=List[schemas.NotificationOut])
def get_notifications(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notifications = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == current_user.id)
        .order_by(models.Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return notifications


@router.patch("/read-all")
def mark_all_read(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id,
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}


@router.post("/device-token")
def register_device_token(
    payload: schemas.DeviceTokenIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = payload.token.strip()
    existing = (
        db.query(models.DeviceToken)
        .filter(models.DeviceToken.token == token)
        .first()
    )
    if existing:
        existing.user_id = current_user.id
        existing.platform = payload.platform
        existing.updated_at = datetime.utcnow()
    else:
        db.add(
            models.DeviceToken(
                user_id=current_user.id,
                token=token,
                platform=payload.platform,
            )
        )
    db.commit()
    return {"ok": True}


@router.delete("/device-token/{token}")
def unregister_device_token(
    token: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(models.DeviceToken).filter(
        models.DeviceToken.token == token,
        models.DeviceToken.user_id == current_user.id,
    ).delete()
    db.commit()
    return {"ok": True}
