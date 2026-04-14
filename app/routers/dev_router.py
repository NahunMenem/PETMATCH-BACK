import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..auth import hash_password

router = APIRouter(prefix="/dev", tags=["dev"])

_SEED_USERS = [
    {
        "email": "seed_max@petmatch.com",
        "name": "Carlos García",
        "pet": {
            "name": "Max",
            "type": models.PetType.dog,
            "breed": "Golden Retriever",
            "age": "2 años",
            "sex": models.PetSex.male,
            "size": models.PetSize.large,
            "vaccines_up_to_date": True,
            "description": "Max es un golden retriever juguetón y cariñoso. Le encanta correr en el parque y jugar con la pelota.",
            "photos": ["https://images.unsplash.com/photo-1552053831-71594a27632d?w=600&q=80"],
        },
    },
    {
        "email": "seed_luna@petmatch.com",
        "name": "Valentina López",
        "pet": {
            "name": "Luna",
            "type": models.PetType.dog,
            "breed": "Husky Siberiano",
            "age": "3 años",
            "sex": models.PetSex.female,
            "size": models.PetSize.large,
            "vaccines_up_to_date": True,
            "description": "Luna es una husky activa y aventurera. Ama los paseos largos y el frío.",
            "photos": ["https://images.unsplash.com/photo-1605568427561-40dd23c2acea?w=600&q=80"],
        },
    },
    {
        "email": "seed_rocky@petmatch.com",
        "name": "Martín Pérez",
        "pet": {
            "name": "Rocky",
            "type": models.PetType.dog,
            "breed": "Labrador",
            "age": "1 año",
            "sex": models.PetSex.male,
            "size": models.PetSize.large,
            "vaccines_up_to_date": False,
            "description": "Rocky es un labrador energético que busca su compañera de juegos perfecta.",
            "photos": ["https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=600&q=80"],
        },
    },
    {
        "email": "seed_mia@petmatch.com",
        "name": "Sofía Martínez",
        "pet": {
            "name": "Mia",
            "type": models.PetType.cat,
            "breed": "Persa",
            "age": "4 años",
            "sex": models.PetSex.female,
            "size": models.PetSize.small,
            "vaccines_up_to_date": True,
            "description": "Mia es una gata persiana tranquila y elegante. Le encanta el sol y las siestas largas.",
            "photos": ["https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=600&q=80"],
        },
    },
]


@router.post("/seed-pets")
def seed_pets(db: Session = Depends(get_db)):
    created = 0
    for entry in _SEED_USERS:
        # Crear usuario si no existe
        user = db.query(models.User).filter(
            models.User.email == entry["email"]
        ).first()
        if not user:
            user = models.User(
                id=str(uuid.uuid4()),
                email=entry["email"],
                hashed_password=hash_password("seed123"),
                name=entry["name"],
            )
            db.add(user)
            db.flush()

        # Borrar datos relacionados para poder recrear la mascota de prueba sin
        # chocar con claves foraneas de likes, matches y chats previos.
        existing_pet_ids = [
            pet_id
            for (pet_id,) in db.query(models.Pet.id)
            .filter(models.Pet.owner_id == user.id)
            .all()
        ]
        if existing_pet_ids:
            conversation_ids = [
                conversation_id
                for (conversation_id,) in db.query(models.Match.conversation_id)
                .filter(
                    or_(
                        models.Match.pet1_id.in_(existing_pet_ids),
                        models.Match.pet2_id.in_(existing_pet_ids),
                    ),
                    models.Match.conversation_id.isnot(None),
                )
                .all()
            ]

            db.query(models.PetLike).filter(
                or_(
                    models.PetLike.liker_pet_id.in_(existing_pet_ids),
                    models.PetLike.liked_pet_id.in_(existing_pet_ids),
                )
            ).delete(synchronize_session=False)

            db.query(models.Match).filter(
                or_(
                    models.Match.pet1_id.in_(existing_pet_ids),
                    models.Match.pet2_id.in_(existing_pet_ids),
                )
            ).delete(synchronize_session=False)

            if conversation_ids:
                db.query(models.Message).filter(
                    models.Message.conversation_id.in_(conversation_ids)
                ).delete(synchronize_session=False)
                db.query(models.Conversation).filter(
                    models.Conversation.id.in_(conversation_ids)
                ).delete(synchronize_session=False)

            db.query(models.Pet).filter(
                models.Pet.id.in_(existing_pet_ids)
            ).delete(synchronize_session=False)

        pet_data = entry["pet"]
        pet = models.Pet(
            id=str(uuid.uuid4()),
            owner_id=user.id,
            name=pet_data["name"],
            type=pet_data["type"],
            breed=pet_data["breed"],
            age=pet_data["age"],
            sex=pet_data["sex"],
            size=pet_data["size"],
            vaccines_up_to_date=pet_data["vaccines_up_to_date"],
            photos=pet_data["photos"],
            description=pet_data["description"],
        )
        db.add(pet)
        created += 1

    db.commit()
    return {"created": created, "message": f"{created} mascotas de prueba creadas"}
