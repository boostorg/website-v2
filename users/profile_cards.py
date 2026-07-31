def user_profile_card(user):
    """Build the dict consumed by v3/includes/_user_profile.html.

    Callers should prefetch "maintainers" on the user, and add
    ``badges.display.active_badges_prefetch()`` whenever they build more than one
    card, or each card costs an extra badge query.
    """
    is_maintainer = bool(user.maintainers.all())
    featured = user.featured_badge
    return {
        "name": user.display_name,
        "profile_url": user.github_profile_url or "",
        "role": "Maintainer" if is_maintainer else "Contributor",
        "avatar_url": user.get_avatar_url(),
        "badge": featured["icon"] if featured else None,
        "badge_label": featured["name"] if featured else "",
    }
