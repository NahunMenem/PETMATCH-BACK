from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleAuth(BaseModel):
    id_token: str
    access_token: Optional[str] = None


class TokenRefresh(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    photo_url: Optional[str]
    location: Optional[str]
    is_verified: bool
    is_premium: bool
    patitas: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


# ── Pet ───────────────────────────────────────────────────────────────────────

class PetCreate(BaseModel):
    name: str
    type: str  # 'dog' | 'cat'
    breed: str
    age: str
    sex: str   # 'male' | 'female'
    size: str  # 'small' | 'medium' | 'large'
    vaccines_up_to_date: bool = False
    sterilized: bool = False
    photos: List[str] = []
    description: Optional[str] = None


class PetUpdate(BaseModel):
    name: Optional[str] = None
    breed: Optional[str] = None
    age: Optional[str] = None
    sex: Optional[str] = None
    size: Optional[str] = None
    vaccines_up_to_date: Optional[bool] = None
    sterilized: Optional[bool] = None
    photos: Optional[List[str]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PetOut(BaseModel):
    id: str
    owner_id: str
    owner_name: str
    owner_photo_url: Optional[str]
    owner_verified: bool
    name: str
    type: str
    breed: str
    age: str
    sex: str
    size: str
    vaccines_up_to_date: bool
    sterilized: bool
    photos: List[str]
    description: Optional[str]
    distance_km: Optional[float]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Swipe ─────────────────────────────────────────────────────────────────────

class SwipeAction(BaseModel):
    pet_id: str  # the pet being liked/disliked


# ── Match ─────────────────────────────────────────────────────────────────────

class MatchOut(BaseModel):
    id: str
    pet_id: str
    pet_name: str
    pet_photo: str
    owner_name: str
    owner_photo: str
    conversation_id: str
    matched_at: datetime


# ── Chat ──────────────────────────────────────────────────────────────────────

class ReceivedLikeOut(BaseModel):
    pet_id: Optional[str] = None
    pet_name: Optional[str] = None
    pet_photo: Optional[str] = None
    owner_name: Optional[str] = None
    liked_my_pet_id: Optional[str] = None
    liked_my_pet_name: Optional[str] = None


class ReceivedLikesOut(BaseModel):
    total: int
    unlocked: bool
    likes: List[ReceivedLikeOut]


class ConversationOut(BaseModel):
    id: str
    match_id: str
    other_user_id: str
    other_user_name: str
    other_user_photo: str
    pet_name: str
    pet_photo: str
    last_message: Optional[str]
    last_message_at: Optional[datetime]
    unread_count: int


class MessageCreate(BaseModel):
    conversation_id: str
    content: str


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    content: str
    is_read: bool
    sent_at: datetime

    class Config:
        from_attributes = True


# ── Adoption ──────────────────────────────────────────────────────────────────

class AdoptionCreate(BaseModel):
    name: str
    type: str
    age: str
    breed: Optional[str] = None
    size: str
    health_status: str
    description: str
    photos: List[str] = []
    location: str


class AdoptionStatusUpdate(BaseModel):
    status: str


class AdoptionOut(BaseModel):
    id: str
    publisher_id: str
    publisher_name: str
    publisher_photo: Optional[str]
    name: str
    type: str
    age: str
    breed: Optional[str]
    size: str
    health_status: str
    description: str
    photos: List[str]
    location: str
    status: str
    published_at: datetime

    class Config:
        from_attributes = True


# ── Notification ──────────────────────────────────────────────────────────────

class LostPetCreate(BaseModel):
    pet_id: Optional[str] = None
    name: str
    type: str
    description: str
    phone: str
    photos: List[str] = []
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    reward_amount: Optional[int] = None
    alert_radius_km: Optional[int] = None


class LostPetStatusUpdate(BaseModel):
    status: str


class LostPetOut(BaseModel):
    id: str
    reporter_id: str
    reporter_name: str
    reporter_photo: Optional[str]
    pet_id: Optional[str]
    name: str
    type: str
    description: str
    phone: str
    photos: List[str]
    location: str
    latitude: Optional[float]
    longitude: Optional[float]
    reward_amount: Optional[int]
    alert_radius_km: Optional[int]
    status: str
    reported_at: datetime
    distance_km: Optional[float] = None

    class Config:
        from_attributes = True


class NotificationOut(BaseModel):
    id: str
    type: str
    title: str
    body: str
    image_url: Optional[str]
    action_id: Optional[str]
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Patitas

class PatitasPackOut(BaseModel):
    id: str
    name: str
    price: int
    base_patitas: int
    bonus_patitas: int
    total_patitas: int


class CrearPreferenciaPatitas(BaseModel):
    pack_id: str


class PreferenciaPatitasOut(BaseModel):
    preference_id: str
    init_point: str
    sandbox_init_point: Optional[str] = None


class PatitasTransactionOut(BaseModel):
    id: str
    usuario_id: str
    tipo: str
    cantidad: int
    descripcion: str
    estado: str
    fecha: datetime

    class Config:
        from_attributes = True


class PatitasWalletOut(BaseModel):
    patitas: int
    transactions: List[PatitasTransactionOut]


class ConsumirPatitasRequest(BaseModel):
    action: str
    descripcion: Optional[str] = None


class ConsumirPatitasOut(BaseModel):
    patitas: int
    transaction: PatitasTransactionOut
