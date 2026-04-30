from fastapi import APIRouter, Query

from ..config import settings

router = APIRouter(prefix="/app", tags=["app"])


@router.get("/version")
def get_app_version(
    platform: str = Query("ios", pattern="^(ios|android)$"),
    version: str = Query("", description="Installed app version"),
    build: str = Query("", description="Installed app build number"),
):
    is_ios = platform == "ios"
    min_version = settings.MIN_IOS_VERSION if is_ios else settings.MIN_ANDROID_VERSION
    latest_version = (
        settings.LATEST_IOS_VERSION if is_ios else settings.LATEST_ANDROID_VERSION
    )
    force_update = settings.FORCE_UPDATE_IOS if is_ios else settings.FORCE_UPDATE_ANDROID

    return {
        "platform": platform,
        "version": version,
        "build": build,
        "min_ios_version": settings.MIN_IOS_VERSION,
        "min_android_version": settings.MIN_ANDROID_VERSION,
        "minimum_version": min_version,
        "latest_ios_version": settings.LATEST_IOS_VERSION,
        "latest_android_version": settings.LATEST_ANDROID_VERSION,
        "latest_version": latest_version,
        "force_update": force_update,
        "required": force_update,
        "message": settings.UPDATE_MESSAGE,
        "app_store_url": settings.APP_STORE_URL,
        "play_store_url": settings.PLAY_STORE_URL,
    }
