import uuid
import requests
from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from ..database import get_db
from .. import models, schemas
from ..auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from ..config import settings
from ..datetime_utils import argentina_now

router = APIRouter(prefix="/auth", tags=["auth"])
REFERRAL_BONUS_PATITAS = 10


def _generate_referral_code() -> str:
    return uuid.uuid4().hex[:8].upper()


def _ensure_referral_code(db: Session, user: models.User) -> None:
    if user.referral_code:
        return

    code = _generate_referral_code()
    while db.query(models.User.id).filter(models.User.referral_code == code).first():
        code = _generate_referral_code()
    user.referral_code = code


def _grant_referral_bonus(
    db: Session,
    *,
    referrer: models.User,
    referred_user: models.User,
) -> None:
    referrer.patitas = (referrer.patitas or 0) + REFERRAL_BONUS_PATITAS
    referred_user.patitas = (referred_user.patitas or 0) + REFERRAL_BONUS_PATITAS

    db.add(
        models.PatitasTransaction(
            id=str(uuid.uuid4()),
            usuario_id=referrer.id,
            tipo=models.PatitasTransactionType.compra,
            cantidad=REFERRAL_BONUS_PATITAS,
            descripcion=f"Bono por referido de {referred_user.email}",
            estado=models.PatitasTransactionStatus.approved,
        )
    )
    db.add(
        models.PatitasTransaction(
            id=str(uuid.uuid4()),
            usuario_id=referred_user.id,
            tipo=models.PatitasTransactionType.compra,
            cantidad=REFERRAL_BONUS_PATITAS,
            descripcion=f"Bono de bienvenida por referido de {referrer.email}",
            estado=models.PatitasTransactionStatus.approved,
        )
    )


def _google_userinfo_from_access_token(access_token: str) -> dict:
    response = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if not response.ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Google invalido",
        )
    return response.json()


def _build_auth_response(user: models.User) -> schemas.AuthResponse:
    return schemas.AuthResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=schemas.UserOut.model_validate(user),
    )


def _require_terms_for_new_account(accepted: bool) -> None:
    if not accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes aceptar los terminos de uso para crear una cuenta",
        )


def _resolve_referrer(db: Session, referral_code: str | None) -> models.User | None:
    if not referral_code:
        return None
    code = referral_code.strip().upper()
    referrer = db.query(models.User).filter(models.User.referral_code == code).first()
    if not referrer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo de referido invalido",
        )
    return referrer


def _verify_apple_identity_token(identity_token: str) -> dict:
    try:
        header = jwt.get_unverified_header(identity_token)
        keys_response = requests.get(
            "https://appleid.apple.com/auth/keys",
            timeout=10,
        )
        keys_response.raise_for_status()
        key = next(
            (
                item
                for item in keys_response.json().get("keys", [])
                if item.get("kid") == header.get("kid")
            ),
            None,
        )
        if key is None:
            raise ValueError("Apple public key not found")
        return jwt.decode(
            identity_token,
            key,
            algorithms=["RS256"],
            audience=settings.APPLE_BUNDLE_ID,
            issuer="https://appleid.apple.com",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Apple invalido",
        )


@router.post("/register", response_model=schemas.AuthResponse)
def register(data: schemas.UserRegister, db: Session = Depends(get_db)):
    _require_terms_for_new_account(data.terms_accepted)
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta con ese email",
        )
    referrer = _resolve_referrer(db, data.referral_code)

    user = models.User(
        id=str(uuid.uuid4()),
        email=data.email,
        hashed_password=hash_password(data.password),
        name=data.name,
        referred_by_user_id=referrer.id if referrer else None,
        terms_accepted_at=argentina_now(),
    )
    _ensure_referral_code(db, user)
    db.add(user)
    db.flush()
    if referrer:
        _grant_referral_bonus(db, referrer=referrer, referred_user=user)
    db.commit()
    db.refresh(user)
    return _build_auth_response(user)


@router.post("/apple", response_model=schemas.AuthResponse)
def apple_auth(data: schemas.AppleAuth, db: Session = Depends(get_db)):
    claims = _verify_apple_identity_token(data.identity_token)

    apple_id = claims.get("sub")
    email = data.email or claims.get("email")
    if not apple_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar la cuenta de Apple",
        )

    user = db.query(models.User).filter(models.User.apple_id == apple_id).first()
    if not user and email:
        user = db.query(models.User).filter(models.User.email == email).first()

    referrer = _resolve_referrer(db, data.referral_code)
    is_new_user = user is None
    if is_new_user:
        _require_terms_for_new_account(data.terms_accepted)
        if not email:
            email = f"{apple_id}@privaterelay.appleid.com"
        user = models.User(
            id=str(uuid.uuid4()),
            email=email,
            apple_id=apple_id,
            name=data.name or email.split("@")[0],
            is_verified=True,
            referred_by_user_id=referrer.id if referrer else None,
            terms_accepted_at=argentina_now(),
        )
        db.add(user)
    else:
        user.apple_id = apple_id
        if user.terms_accepted_at is None and data.terms_accepted:
            user.terms_accepted_at = argentina_now()

    _ensure_referral_code(db, user)
    db.flush()
    if is_new_user and referrer:
        _grant_referral_bonus(db, referrer=referrer, referred_user=user)
    db.commit()
    db.refresh(user)
    return _build_auth_response(user)


@router.post("/login", response_model=schemas.AuthResponse)
def login(data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contrasena incorrectos",
        )
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contrasena incorrectos",
        )
    return _build_auth_response(user)


@router.post("/google", response_model=schemas.AuthResponse)
def google_auth(data: schemas.GoogleAuth, db: Session = Depends(get_db)):
    if not data.id_token and not data.access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Faltan credenciales de Google",
        )

    info = None

    if data.id_token:
        try:
            info = id_token.verify_oauth2_token(
                data.id_token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID or None,
            )
        except ValueError:
            info = None

    if info is None and data.access_token:
        info = _google_userinfo_from_access_token(data.access_token)

    if info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Google invalido",
        )

    google_id = info.get("sub")
    email = info.get("email", "")
    name = info.get("name", email.split("@")[0])
    photo_url = info.get("picture")
    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar la cuenta de Google",
        )

    user = db.query(models.User).filter(models.User.google_id == google_id).first()
    if not user:
        user = db.query(models.User).filter(models.User.email == email).first()
    referrer = _resolve_referrer(db, data.referral_code)
    is_new_user = user is None
    if is_new_user:
        _require_terms_for_new_account(data.terms_accepted)
    if not user:
        user = models.User(
            id=str(uuid.uuid4()),
            email=email,
            google_id=google_id,
            name=name,
            photo_url=photo_url,
            is_verified=True,
            referred_by_user_id=referrer.id if referrer else None,
            terms_accepted_at=argentina_now(),
        )
        db.add(user)
    else:
        user.google_id = google_id
        if photo_url and not user.photo_url:
            user.photo_url = photo_url
    _ensure_referral_code(db, user)
    db.flush()
    if is_new_user and referrer:
        _grant_referral_bonus(db, referrer=referrer, referred_user=user)
    db.commit()
    db.refresh(user)
    return _build_auth_response(user)


@router.post("/refresh", response_model=schemas.AuthResponse)
def refresh_token(data: schemas.TokenRefresh, db: Session = Depends(get_db)):
    user_id = decode_token(data.refresh_token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalido",
        )
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )
    return _build_auth_response(user)


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.delete("/me")
def delete_me(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    pet_ids = [
        pet_id
        for (pet_id,) in db.query(models.Pet.id)
        .filter(models.Pet.owner_id == user_id)
        .all()
    ]
    conversation_ids = [
        conv_id
        for (conv_id,) in db.query(models.Conversation.id)
        .filter(
            (models.Conversation.user1_id == user_id)
            | (models.Conversation.user2_id == user_id)
        )
        .all()
    ]

    db.query(models.ContentReport).filter(
        (models.ContentReport.reporter_id == user_id)
        | (models.ContentReport.reported_user_id == user_id)
    ).delete(synchronize_session=False)
    db.query(models.UserBlock).filter(
        (models.UserBlock.blocker_id == user_id)
        | (models.UserBlock.blocked_user_id == user_id)
    ).delete(synchronize_session=False)
    db.query(models.Notification).filter(models.Notification.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(models.DeviceToken).filter(models.DeviceToken.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(models.PatitasTransaction).filter(
        models.PatitasTransaction.usuario_id == user_id
    ).delete(synchronize_session=False)
    db.query(models.Adoption).filter(models.Adoption.publisher_id == user_id).delete(
        synchronize_session=False
    )
    db.query(models.LostPet).filter(models.LostPet.reporter_id == user_id).delete(
        synchronize_session=False
    )
    if conversation_ids:
        db.query(models.Message).filter(
            models.Message.conversation_id.in_(conversation_ids)
        ).delete(synchronize_session=False)
        db.query(models.Match).filter(
            models.Match.conversation_id.in_(conversation_ids)
        ).delete(synchronize_session=False)
        db.query(models.Conversation).filter(
            models.Conversation.id.in_(conversation_ids)
        ).delete(synchronize_session=False)
    if pet_ids:
        db.query(models.LostPet).filter(models.LostPet.pet_id.in_(pet_ids)).update(
            {"pet_id": None},
            synchronize_session=False,
        )
        db.query(models.PetLike).filter(
            (models.PetLike.liker_pet_id.in_(pet_ids))
            | (models.PetLike.liked_pet_id.in_(pet_ids))
        ).delete(synchronize_session=False)
        db.query(models.Match).filter(
            (models.Match.pet1_id.in_(pet_ids)) | (models.Match.pet2_id.in_(pet_ids))
        ).delete(synchronize_session=False)
        db.query(models.Pet).filter(models.Pet.id.in_(pet_ids)).delete(
            synchronize_session=False
        )
    db.query(models.User).filter(models.User.referred_by_user_id == user_id).update(
        {"referred_by_user_id": None},
        synchronize_session=False,
    )
    db.delete(current_user)
    db.commit()
    return {"ok": True}


@router.get("/referral/me", response_model=schemas.ReferralSummaryOut)
def my_referral_summary(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_referral_code(db, current_user)
    db.commit()
    db.refresh(current_user)

    referred_count = (
        db.query(models.User.id)
        .filter(models.User.referred_by_user_id == current_user.id)
        .count()
    )
    earned_patitas = referred_count * REFERRAL_BONUS_PATITAS
    share_message = (
        f"Sumate a PawMatch con mi codigo {current_user.referral_code} y ganamos "
        f"{REFERRAL_BONUS_PATITAS} Patitas cada uno."
    )
    return schemas.ReferralSummaryOut(
        referral_code=current_user.referral_code,
        referred_count=referred_count,
        earned_patitas=earned_patitas,
        share_message=share_message,
    )


@router.patch("/me/location", response_model=schemas.UserOut)
def update_location(
    data: schemas.UserLocationUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.latitude = data.latitude
    current_user.longitude = data.longitude
    if data.location is not None:
        current_user.location = data.location
    db.commit()
    db.refresh(current_user)
    return current_user
