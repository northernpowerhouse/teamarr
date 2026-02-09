"""Gold Zone settings endpoints (Olympics Special Feature)."""

from fastapi import APIRouter

from teamarr.database import get_db

from .models import GoldZoneSettingsModel, GoldZoneSettingsUpdate

router = APIRouter()


@router.get("/settings/gold-zone", response_model=GoldZoneSettingsModel)
def get_gold_zone_settings():
    """Get Gold Zone settings."""
    from teamarr.database.settings import get_gold_zone_settings

    with get_db() as conn:
        settings = get_gold_zone_settings(conn)

    return GoldZoneSettingsModel(
        enabled=settings.enabled,
        channel_number=settings.channel_number,
    )


@router.put("/settings/gold-zone", response_model=GoldZoneSettingsModel)
def update_gold_zone_settings(update: GoldZoneSettingsUpdate):
    """Update Gold Zone settings."""
    from teamarr.database.settings import get_gold_zone_settings
    from teamarr.database.settings import update_gold_zone_settings as db_update

    with get_db() as conn:
        db_update(
            conn,
            enabled=update.enabled,
            channel_number=update.channel_number,
        )

    with get_db() as conn:
        settings = get_gold_zone_settings(conn)

    return GoldZoneSettingsModel(
        enabled=settings.enabled,
        channel_number=settings.channel_number,
    )
