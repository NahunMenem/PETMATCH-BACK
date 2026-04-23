import json
import os
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from . import models

_firebase_ready: Optional[bool] = None


def _ensure_firebase() -> bool:
    global _firebase_ready
    if _firebase_ready is not None:
        return _firebase_ready

    try:
        import firebase_admin
        from firebase_admin import credentials

        if firebase_admin._apps:
            _firebase_ready = True
            return True

        service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        if service_account_json:
            cred = credentials.Certificate(json.loads(service_account_json))
        else:
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if not credentials_path:
                _firebase_ready = False
                return False
            cred = credentials.Certificate(credentials_path)

        firebase_admin.initialize_app(cred)
        _firebase_ready = True
        return True
    except Exception:
        _firebase_ready = False
        return False


def send_push_to_user(
    db: Session,
    *,
    user_id: str,
    title: str,
    body: str,
    image_url: Optional[str] = None,
    data: Optional[dict] = None,
) -> None:
    if not _ensure_firebase():
        return

    from firebase_admin import messaging

    tokens = [
        token
        for (token,) in db.query(models.DeviceToken.token)
        .filter(models.DeviceToken.user_id == user_id)
        .all()
    ]
    if not tokens:
        return

    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(
            title=title,
            body=body,
            image=image_url,
        ),
        data={key: str(value) for key, value in (data or {}).items() if value is not None},
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="alerta.caf")
            )
        ),
    )

    try:
        response = messaging.send_each_for_multicast(message)
    except Exception:
        return

    _remove_invalid_tokens(db, tokens, response.responses)


def _remove_invalid_tokens(db: Session, tokens: Iterable[str], responses) -> None:
    invalid_tokens = []
    for token, result in zip(tokens, responses):
        if result.success:
            continue
        code = getattr(result.exception, "code", "") or ""
        if code in {
            "registration-token-not-registered",
            "invalid-registration-token",
        }:
            invalid_tokens.append(token)

    if invalid_tokens:
        db.query(models.DeviceToken).filter(
            models.DeviceToken.token.in_(invalid_tokens)
        ).delete(synchronize_session=False)
