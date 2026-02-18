import structlog
from django.contrib.auth import get_user_model

from badges.calculators import get_calculators
from badges.models import Badge
from badges.utils import award_user_badges
from config.celery import app

logger = structlog.getLogger(__name__)


User = get_user_model()


@app.task
def update_badges():
    """Update or create Badge rows in the database for each calculator class."""
    logger.info("Starting badges updates")
    for calculator_class in get_calculators():
        class_reference = calculator_class.class_reference
        logger.info(f"Updating {class_reference=}, validating...")
        try:
            calculator_class.validate()
        except NotImplementedError as e:
            logger.error(f"FAILED badge update: {e}")
            continue
        logger.info(f"Updating {class_reference=}, valid. Updating...")
        badge, created = Badge.objects.update_or_create(
            calculator_class_reference=class_reference,
            defaults={
                "title": calculator_class.title,
                "display_name": calculator_class.display_name,
                "description": calculator_class.description or "",
                "image_light": calculator_class.badge_image_light,
                "image_dark": calculator_class.badge_image_dark,
                "image_small_light": calculator_class.badge_image_small_light,
                "image_small_dark": calculator_class.badge_image_small_dark,
                "is_nft_enabled": calculator_class.is_nft_enabled,
            },
        )
        logger.info(f"{'Created' if created else 'Updated'} {class_reference=} badge")


@app.task
def award_badges(user_id: int | None = None) -> None:
    """Calculate and award badges to users based on their contributions."""
    logger.info("Starting badges calculation")
    if user_id:
        users = User.objects.filter(pk=user_id)
    else:
        users = User.objects.all()

    for user in users:
        award_user_badges(user)

    logger.info("Badge calculation completed")
