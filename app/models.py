import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, Float, Integer,
    ForeignKey, Text, Enum, ARRAY
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY as PG_ARRAY
import enum
from .database import Base


def gen_uuid():
    return str(uuid.uuid4())


class PetType(str, enum.Enum):
    dog = "dog"
    cat = "cat"


class PetSex(str, enum.Enum):
    male = "male"
    female = "female"


class PetSize(str, enum.Enum):
    small = "small"
    medium = "medium"
    large = "large"


class AdoptionStatus(str, enum.Enum):
    available = "available"
    reserved = "reserved"
    adopted = "adopted"


class LostPetStatus(str, enum.Enum):
    active = "active"
    found = "found"
    closed = "closed"


class PatitasTransactionType(str, enum.Enum):
    compra = "compra"
    uso = "uso"


class PatitasTransactionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    used = "used"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)  # null for Google users
    name = Column(String, nullable=False)
    photo_url = Column(String, nullable=True)
    location = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_verified = Column(Boolean, default=False)
    is_premium = Column(Boolean, default=False)
    patitas = Column(Integer, nullable=False, default=0)
    google_id = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pets = relationship("Pet", back_populates="owner", lazy="dynamic")
    adoptions = relationship("Adoption", back_populates="publisher", lazy="dynamic")
    lost_pet_reports = relationship("LostPet", back_populates="reporter", lazy="dynamic")
    patitas_transactions = relationship(
        "PatitasTransaction", back_populates="user", lazy="dynamic"
    )


class PatitasTransaction(Base):
    __tablename__ = "transacciones_patitas"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    tipo = Column(Enum(PatitasTransactionType), nullable=False)
    cantidad = Column(Integer, nullable=False)
    descripcion = Column(Text, nullable=False)
    estado = Column(Enum(PatitasTransactionStatus), nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False)
    mercado_pago_preference_id = Column(String, nullable=True, index=True)
    mercado_pago_payment_id = Column(String, nullable=True, unique=True, index=True)
    pack_id = Column(String, nullable=True)

    user = relationship("User", back_populates="patitas_transactions")


class Pet(Base):
    __tablename__ = "pets"

    id = Column(String, primary_key=True, default=gen_uuid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(Enum(PetType), nullable=False)
    breed = Column(String, nullable=False)
    age = Column(String, nullable=False)
    sex = Column(Enum(PetSex), nullable=False)
    size = Column(Enum(PetSize), nullable=False)
    vaccines_up_to_date = Column(Boolean, default=False)
    sterilized = Column(Boolean, default=False)
    photos = Column(PG_ARRAY(String), default=[])
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="pets")
    likes_received = relationship(
        "PetLike", foreign_keys="PetLike.liked_pet_id", back_populates="liked_pet"
    )
    likes_given = relationship(
        "PetLike", foreign_keys="PetLike.liker_pet_id", back_populates="liker_pet"
    )


class PetLike(Base):
    __tablename__ = "pet_likes"

    id = Column(String, primary_key=True, default=gen_uuid)
    liker_pet_id = Column(String, ForeignKey("pets.id"), nullable=False)
    liked_pet_id = Column(String, ForeignKey("pets.id"), nullable=False)
    is_dislike = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    liker_pet = relationship("Pet", foreign_keys=[liker_pet_id], back_populates="likes_given")
    liked_pet = relationship("Pet", foreign_keys=[liked_pet_id], back_populates="likes_received")


class Match(Base):
    __tablename__ = "matches"

    id = Column(String, primary_key=True, default=gen_uuid)
    pet1_id = Column(String, ForeignKey("pets.id"), nullable=False)
    pet2_id = Column(String, ForeignKey("pets.id"), nullable=False)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
    matched_at = Column(DateTime, default=datetime.utcnow)

    pet1 = relationship("Pet", foreign_keys=[pet1_id])
    pet2 = relationship("Pet", foreign_keys=[pet2_id])
    conversation = relationship("Conversation", back_populates="match")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=gen_uuid)
    user1_id = Column(String, ForeignKey("users.id"), nullable=False)
    user2_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user1 = relationship("User", foreign_keys=[user1_id])
    user2 = relationship("User", foreign_keys=[user2_id])
    messages = relationship("Message", back_populates="conversation", lazy="dynamic")
    match = relationship("Match", back_populates="conversation", uselist=False)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    sender_id = Column(String, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    sent_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])


class Adoption(Base):
    __tablename__ = "adoptions"

    id = Column(String, primary_key=True, default=gen_uuid)
    publisher_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(Enum(PetType), nullable=False)
    age = Column(String, nullable=False)
    breed = Column(String, nullable=True)
    size = Column(Enum(PetSize), nullable=False)
    health_status = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    photos = Column(PG_ARRAY(String), default=[])
    location = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    phone = Column(String, nullable=False, default="")
    status = Column(Enum(AdoptionStatus), default=AdoptionStatus.available)
    published_at = Column(DateTime, default=datetime.utcnow)

    publisher = relationship("User", back_populates="adoptions")


class LostPet(Base):
    __tablename__ = "lost_pets"

    id = Column(String, primary_key=True, default=gen_uuid)
    reporter_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    pet_id = Column(String, ForeignKey("pets.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    type = Column(Enum(PetType), nullable=False)
    description = Column(Text, nullable=False)
    phone = Column(String, nullable=False)
    photos = Column(PG_ARRAY(String), default=[])
    location = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    reward_amount = Column(Integer, nullable=True)
    alert_radius_km = Column(Integer, nullable=True)
    status = Column(Enum(LostPetStatus), default=LostPetStatus.active, nullable=False)
    reported_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reporter = relationship("User", back_populates="lost_pet_reports")
    pet = relationship("Pet")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)
    action_id = Column(String, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    token = Column(String, nullable=False, unique=True, index=True)
    platform = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
