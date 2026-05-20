def user_profile_card(user):
    """Build the dict consumed by v3/includes/_user_profile.html.

    Callers should prefetch "maintainers" on the user.
    """
    is_maintainer = bool(user.maintainers.all())
    return {
        "name": user.display_name,
        "profile_url": user.github_profile_url or "",
        "role": "Maintainer" if is_maintainer else "Contributor",
        "avatar_url": user.get_avatar_url(),
        # Placeholder until real per-user badge data lands; matches the
        # /news/ post list, which reads User.badge_url directly.
        "badge_url": user.badge_url,
    }
