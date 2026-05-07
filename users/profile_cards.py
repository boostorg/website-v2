from django.conf import settings


def user_profile_card(user):
    """Build the dict consumed by v3/includes/_user_profile.html.

    Truthiness checks (rather than .exists() / .filter() with kwargs)
    so prefetch_related caches are reused. Callers should prefetch
    "badges" and "maintainers" on the user.
    """
    is_maintainer = bool(user.maintainers.all())
    badges = list(user.badges.all())
    badge = badges[0] if badges else None
    badge_url = (
        f"{settings.STATIC_URL}img/v3/badges/badge-{badge.name}.png"
        if badge and badge.name
        else ""
    )
    return {
        "name": user.display_name,
        "profile_url": user.github_profile_url or "",
        "role": "Maintainer" if is_maintainer else "Contributor",
        "avatar_url": user.get_avatar_url(),
        "badge_url": badge_url,
    }
