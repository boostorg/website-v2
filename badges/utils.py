import structlog
from django.contrib.auth import get_user_model

from badges.calculators import get_calculators
from badges.models import Badge, UserBadge

logger = structlog.getLogger(__name__)

User = get_user_model()


def award_user_badges(user: User) -> None:
    """
    Calculate and update all badges for a specific user.

    Args:
        user: The User instance to calculate badges for
    """
    logger.info(f"Starting badge calculations for user_id={user.id}")
    for calculator_class in get_calculators():
        try:
            calculator = calculator_class(user)
        except NotImplementedError as e:
            logger.error(f"FAILED instantiating badge calculator: {e}")
            continue
        class_reference = calculator_class.class_reference

        try:
            badge = Badge.objects.get(calculator_class_reference=class_reference)
        except Badge.DoesNotExist:
            logger.warning(f"No badge with {class_reference=}. Run update_badges task")
            continue

        if calculator.achieved:
            grade = calculator.grade
            defaults = {"grade": grade}

            if not badge.is_nft_enabled:
                defaults["published"] = True
                defaults["approved"] = True

            _, created = UserBadge.objects.update_or_create(
                user=user,
                badge=badge,
                defaults=defaults,
            )
            change = "Created" if created else "Updated"
            logger.info(f"{change} {class_reference} UserBadge, {user.id=} {grade=}")
        else:
            # badge not achieved, remove it if it exists
            UserBadge.objects.filter(user=user, badge=badge).delete()
            logger.info(f"Deleted {class_reference} UserBadge for {user.id=}")

    logger.info(f"Completed badge calculations for user_id={user.id}")
