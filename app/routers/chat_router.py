import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from ..database import get_db
from .. import models, schemas
from ..auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/conversations", response_model=List[schemas.ConversationOut])
def get_conversations(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversations = db.query(models.Conversation).filter(
        or_(
            models.Conversation.user1_id == current_user.id,
            models.Conversation.user2_id == current_user.id,
        )
    ).all()

    result = []
    for conv in conversations:
        other_user = (
            conv.user2 if conv.user1_id == current_user.id else conv.user1
        )

        # Last message
        last_msg = (
            db.query(models.Message)
            .filter(models.Message.conversation_id == conv.id)
            .order_by(models.Message.sent_at.desc())
            .first()
        )

        # Unread count
        unread = (
            db.query(func.count(models.Message.id))
            .filter(
                models.Message.conversation_id == conv.id,
                models.Message.sender_id != current_user.id,
                models.Message.is_read == False,
            )
            .scalar()
        )

        # Match info for pet details
        match = conv.match
        pet_name = ""
        pet_photo = ""
        match_id = ""
        if match:
            match_id = match.id
            pet = (
                match.pet1
                if match.pet1.owner_id != current_user.id
                else match.pet2
            )
            pet_name = pet.name
            pet_photo = pet.photos[0] if pet.photos else ""

        result.append(
            schemas.ConversationOut(
                id=conv.id,
                match_id=match_id,
                other_user_id=other_user.id,
                other_user_name=other_user.name,
                other_user_photo=other_user.photo_url or "",
                pet_name=pet_name,
                pet_photo=pet_photo,
                last_message=last_msg.content if last_msg else None,
                last_message_at=last_msg.sent_at if last_msg else None,
                unread_count=unread or 0,
            )
        )

    return result


@router.get("/messages/{conversation_id}", response_model=List[schemas.MessageOut])
def get_messages(
    conversation_id: str,
    page: int = Query(1, ge=1),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        or_(
            models.Conversation.user1_id == current_user.id,
            models.Conversation.user2_id == current_user.id,
        ),
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    messages = (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conversation_id)
        .order_by(models.Message.sent_at.asc())
        .offset((page - 1) * 50)
        .limit(50)
        .all()
    )
    return messages


@router.post("/messages", response_model=schemas.MessageOut)
def send_message(
    data: schemas.MessageCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == data.conversation_id,
        or_(
            models.Conversation.user1_id == current_user.id,
            models.Conversation.user2_id == current_user.id,
        ),
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    msg = models.Message(
        id=str(uuid.uuid4()),
        conversation_id=data.conversation_id,
        sender_id=current_user.id,
        content=data.content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.patch("/conversations/{conversation_id}/read")
def mark_read(
    conversation_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(models.Message).filter(
        models.Message.conversation_id == conversation_id,
        models.Message.sender_id != current_user.id,
        models.Message.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}
