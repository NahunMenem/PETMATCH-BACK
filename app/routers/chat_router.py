import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from ..database import get_db
from .. import models, schemas
from ..auth import get_current_user
from ..notification_service import TYPE_NEW_MESSAGE, create_notification
from ..moderation import validate_clean_text

router = APIRouter(prefix="/chat", tags=["chat"])


def _blocked_user_ids(db: Session, user_id: str) -> set[str]:
    blocked = db.query(models.UserBlock.blocked_user_id).filter(
        models.UserBlock.blocker_id == user_id
    ).all()
    blocked_by = db.query(models.UserBlock.blocker_id).filter(
        models.UserBlock.blocked_user_id == user_id
    ).all()
    return {row[0] for row in blocked + blocked_by}


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
    blocked_user_ids = _blocked_user_ids(db, current_user.id)
    for conv in conversations:
        other_user = (
            conv.user2 if conv.user1_id == current_user.id else conv.user1
        )
        if other_user.id in blocked_user_ids:
            continue

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
    other_user_id = conv.user2_id if conv.user1_id == current_user.id else conv.user1_id
    if other_user_id in _blocked_user_ids(db, current_user.id):
        raise HTTPException(status_code=403, detail="Usuario bloqueado")

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
    validate_clean_text(data.content)
    receiver_id = conv.user2_id if conv.user1_id == current_user.id else conv.user1_id
    if receiver_id in _blocked_user_ids(db, current_user.id):
        raise HTTPException(status_code=403, detail="Usuario bloqueado")

    msg = models.Message(
        id=str(uuid.uuid4()),
        conversation_id=data.conversation_id,
        sender_id=current_user.id,
        content=data.content,
    )
    db.add(msg)
    create_notification(
        db,
        user_id=receiver_id,
        type=TYPE_NEW_MESSAGE,
        title="Nuevo mensaje",
        body=f"{current_user.name}: \"{data.content[:80]}\"",
        image_url=current_user.photo_url,
        action_id=conv.id,
    )
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


@router.post("/report")
def report_conversation(
    data: schemas.ConversationModerationAction,
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
    other_user_id = conv.user2_id if conv.user1_id == current_user.id else conv.user1_id
    db.add(
        models.ContentReport(
            id=str(uuid.uuid4()),
            reporter_id=current_user.id,
            reported_user_id=other_user_id,
            content_type="conversation",
            content_id=conv.id,
            reason=data.reason or "Contenido inapropiado",
        )
    )
    db.commit()
    return {"ok": True}


@router.post("/block-user")
def block_conversation_user(
    data: schemas.ConversationModerationAction,
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
    other_user_id = conv.user2_id if conv.user1_id == current_user.id else conv.user1_id
    existing = db.query(models.UserBlock).filter(
        models.UserBlock.blocker_id == current_user.id,
        models.UserBlock.blocked_user_id == other_user_id,
    ).first()
    if not existing:
        db.add(
            models.UserBlock(
                id=str(uuid.uuid4()),
                blocker_id=current_user.id,
                blocked_user_id=other_user_id,
                reason=data.reason,
            )
        )
    db.add(
        models.ContentReport(
            id=str(uuid.uuid4()),
            reporter_id=current_user.id,
            reported_user_id=other_user_id,
            content_type="user",
            content_id=other_user_id,
            reason=data.reason or "Usuario bloqueado por conducta abusiva",
        )
    )
    db.commit()
    return {"ok": True}
