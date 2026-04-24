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


_SEED_SHOPS = [
    {"nombre": "Pet Palace", "tipo": "petshop", "descripcion": "La pet shop más completa del barrio. Alimentos premium, accesorios, juguetes y asesoramiento experto para tu mascota. Delivery disponible.", "direccion": "Av. Corrientes 1890, CABA", "lat": -34.6037, "lng": -58.3816, "telefono_whatsapp": "5491122334455", "rating": 4.8, "promo": "10% OFF en alimento esta semana", "es_destacado": True, "es_aliado": True},
    {"nombre": "VetCare Palermo", "tipo": "veterinaria", "descripcion": "Clínica veterinaria con más de 10 años de experiencia. Urgencias 24hs, cirugía, laboratorio y radiografías.", "direccion": "Thames 1456, Palermo", "lat": -34.5891, "lng": -58.4231, "telefono_whatsapp": "5491133445566", "rating": 4.9, "promo": "1ª consulta gratis para nuevos pacientes", "es_destacado": True, "es_aliado": True},
    {"nombre": "Mundo Mascota", "tipo": "petshop", "descripcion": "Todo lo que necesita tu mascota en un solo lugar. Más de 5000 productos disponibles.", "direccion": "Av. Santa Fe 2145, Palermo", "lat": -34.5950, "lng": -58.4000, "telefono_whatsapp": "5491144556677", "rating": 4.7, "promo": "15% OFF en bolsas de alimento", "es_destacado": False, "es_aliado": True},
    {"nombre": "Clínica Vet San Martín", "tipo": "veterinaria", "descripcion": "Atención integral para perros y gatos. Vacunación, castración, internación y emergencias.", "direccion": "Gurruchaga 890, Villa Crespo", "lat": -34.6010, "lng": -58.4350, "telefono_whatsapp": "5491155667788", "rating": 4.9, "promo": None, "es_destacado": False, "es_aliado": False},
    {"nombre": "Grooming Studio", "tipo": "peluqueria", "descripcion": "Baño, corte y estética canina. Usamos productos naturales hipoalergénicos. Turnos online disponibles.", "direccion": "Av. Cabildo 2300, Belgrano", "lat": -34.5650, "lng": -58.4550, "telefono_whatsapp": "5491166778899", "rating": 4.6, "promo": "Baño + corte $5000 hasta fin de mes", "es_destacado": True, "es_aliado": True},
    {"nombre": "Paseos Caninos BA", "tipo": "paseador", "descripcion": "Paseos grupales e individuales. GPS en tiempo real, foto al finalizar cada paseo. Cobertura en Palermo, Belgrano y Recoleta.", "direccion": "Palermo, CABA", "lat": -34.5785, "lng": -58.4240, "telefono_whatsapp": "5491177889900", "rating": 4.8, "promo": "1er paseo gratis", "es_destacado": False, "es_aliado": True},
    {"nombre": "Hotel Canino El Refugio", "tipo": "guarderia", "descripcion": "Guardería y hotel para mascotas. Amplio espacio verde, cámaras 24hs y atención personalizada.", "direccion": "Av. Libertador 5000, Núñez", "lat": -34.5520, "lng": -58.4620, "telefono_whatsapp": "5491188990011", "rating": 4.5, "promo": "10% OFF guardería semanal", "es_destacado": True, "es_aliado": True},
    {"nombre": "Vet Express", "tipo": "veterinaria", "descripcion": "Atención rápida sin turno previo. Consultas express, vacunación y laboratorio.", "direccion": "Av. Rivadavia 3500, Flores", "lat": -34.6200, "lng": -58.4700, "telefono_whatsapp": None, "rating": 4.3, "promo": None, "es_destacado": False, "es_aliado": False},
]


@router.post("/seed-shops")
def seed_shops(db: Session = Depends(get_db)):
    created = 0
    for data in _SEED_SHOPS:
        existing = db.query(models.Shop).filter(models.Shop.nombre == data["nombre"]).first()
        if not existing:
            shop = models.Shop(
                id=str(uuid.uuid4()),
                nombre=data["nombre"],
                tipo=data["tipo"],
                descripcion=data.get("descripcion"),
                direccion=data["direccion"],
                lat=data["lat"],
                lng=data["lng"],
                telefono_whatsapp=data.get("telefono_whatsapp"),
                rating=data.get("rating"),
                promo=data.get("promo"),
                es_destacado=data.get("es_destacado", False),
                es_aliado=data.get("es_aliado", False),
                activo=True,
            )
            db.add(shop)
            created += 1
    db.commit()
    return {"created": created, "message": f"{created} shops creados"}
