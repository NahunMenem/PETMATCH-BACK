import math
from typing import Optional

from sqlalchemy.orm import Session

from . import models


TYPE_NEW_MATCH = "new_match"
TYPE_NEW_MESSAGE = "new_message"
TYPE_ADOPTION_INTEREST = "adoption_interest"
TYPE_LOST_PET_NEARBY = "lost_pet_nearby"
TYPE_LOST_ALERT_REACH = "lost_alert_reach"
TYPE_PROFILE_TIP = "profile_tip"
TYPE_LIKE = "like"
TYPE_PATITAS = "patitas"


def create_notification(
    db: Session,
    *,
    user_id: str,
    type: str,
    title: str,
    body: str,
    image_url: Optional[str] = None,
    action_id: Optional[str] = None,
) -> models.Notification:
    notification = models.Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        image_url=image_url,
        action_id=action_id,
    )
    db.add(notification)
    return notification


def distance_km(
    lat1: Optional[float],
    lng1: Optional[float],
    lat2: Optional[float],
    lng2: Optional[float],
) -> Optional[float]:
    if None in (lat1, lng1, lat2, lng2):
        return None
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return round(radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)


def notify_users_near_lost_pet(
    db: Session,
    *,
    lost_pet: models.LostPet,
    radius_km: int,
) -> int:
    if lost_pet.latitude is None or lost_pet.longitude is None:
        return 0

    users = (
        db.query(models.User)
        .filter(
            models.User.id != lost_pet.reporter_id,
            models.User.latitude.isnot(None),
            models.User.longitude.isnot(None),
        )
        .all()
    )

    notified = 0
    for user in users:
        distance = distance_km(
            user.latitude,
            user.longitude,
            lost_pet.latitude,
            lost_pet.longitude,
        )
        if distance is None or distance > radius_km:
            continue
        create_notification(
            db,
            user_id=user.id,
            type=TYPE_LOST_PET_NEARBY,
            title="Mascota perdida cerca",
            body=(
                f"Se perdio {lost_pet.name} a "
                f"{distance:.1f} km de tu ubicacion."
            ),
            image_url=(lost_pet.photos or [None])[0],
            action_id=lost_pet.id,
        )
        notified += 1

    return notified
