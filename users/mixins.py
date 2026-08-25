from urllib.parse import urlparse

from badges import display as badge_display
from core.context_processors import edit_profile_url
from users.profile_cards import github_activity_card_context


class V3UserProfileContextMixin:
    """Read-only v3 profile context, shared by the public profile page and by
    the logged-in user's own (non-editable) view of their profile.

    Both pages render `v3/user_profile_page.html` from the same data. They
    differ only in the header button trailing the profile links: visitors get
    Share Profile, the profile's owner gets Edit Profile (see
    `get_trailing_button()`), and only the owner's view carries the account
    connections card.
    """

    # Header buttons that link out to the public profile links a user has
    # set, in display order. Each entry maps a profile_links key to the
    # button label and icon; the stored value becomes the button's href.
    V3_PROFILE_LINK_BUTTONS = [
        ("github", "GitHub", "pixel-github"),
        ("website", "Website", "pixel-computer"),
        ("email", "Email", "pixel-email"),
        ("slack", "Chat on Slack", "pixel-slack"),
    ]

    @staticmethod
    def _safe_web_url(value):
        """Return a safe http(s) href for a stored profile-link value, or None.

        Profile-link values are stored as plain text with no scheme
        validation, so they are untrusted. Rendering them straight into an
        `href` would allow a `javascript:`/`data:` value to execute when a
        visitor clicks the link. Only http(s) URLs are allowed through;
        scheme-less values (e.g. "example.com") are treated as https."""
        value = value.strip()
        scheme = urlparse(value).scheme.lower()
        if scheme in ("http", "https"):
            return value
        if not scheme:
            return f"https://{value}"
        return None

    def get_trailing_button(self, user):
        """The header button that follows the profile links.

        Owners get Edit Profile in place of Share Profile, on both
        `/users/me/` and their own `/users/<pk>/` page, so the affordance
        follows who is looking rather than which route was used. Share
        Profile is therefore only ever reachable on someone else's public
        profile."""
        if user == self.request.user:
            return {
                "label": "Edit Profile",
                "url": edit_profile_url(),
                "icon": "pixel-pencil",
            }
        return {"label": "Share Profile", "url": "#", "icon": "pixel-share"}

    def get_v3_profile_link_buttons(self, user):
        """Header buttons for the public profile links the user has set.

        Links with no (or an unsafe) value are omitted, since only populated
        links are shown publicly. The list always ends with the trailing
        button."""
        links = user.profile_links or {}
        buttons = []
        for key, label, icon in self.V3_PROFILE_LINK_BUTTONS:
            value = links.get(key)
            if not value:
                continue
            if key == "email":
                url = f"mailto:{value.strip()}"
            else:
                url = self._safe_web_url(value)
                if url is None:
                    continue
            buttons.append({"label": label, "url": url, "icon": icon})
        buttons.append(self.get_trailing_button(user))
        return buttons

    def get_v3_public_context(self, user):
        """Context for the read-only v3 profile view.

        Renders real user data. Sections with no underlying data (GitHub
        activity, mailing list activity, posts, achievements) are left out
        of the context so the template omits them entirely. The bio section
        is always rendered, falling back to an empty state."""
        is_owner = user == self.request.user
        context = {
            "user_info": {
                "user_name": user.display_name,
                "avatar_url": user.get_avatar_url(),
                "member_since": user.year_joined,
                # `public_role` ignores the hide-public-role opt-out, so it is
                # only ever right on the owner's own view of their page.
                # Serving it to a visitor would publish the very role the
                # opt-out exists to withhold; they get `role`, which honours it.
                "role": (user.public_role if is_owner else user.role),
                "flag_emoji": user.flag_emoji,
                # include_hidden only for the owner, for the same reason as
                # `role`: a member who hid their badges still sees them on
                # their own page, and a visitor never does.
                "featured_badge": badge_display.featured_badge(
                    user, include_hidden=is_owner
                ),
            },
            "profile_badges": badge_display.badge_cards(user, include_hidden=is_owner),
            # The recognition cards render on the owner's own page even when
            # empty, because their empty states are the way in to the badge and
            # achievement dialogs. A visitor sees them only with real data.
            "profile_is_owner": is_owner,
            # Library contributions grouped by role, rendered as the
            # contributions section of the bio card. An empty dict means no
            # contributions, and the card omits the section.
            "contributor_data": user.get_contributor_data(),
            # None (rather than "") when the user has no biography, so the
            # template renders the bio empty state instead of an empty card.
            # A stored biography is Markdown; the bio card renders it.
            "bio": user.biography or None,
            "top_links": self.get_v3_profile_link_buttons(user),
        }
        # Owner-only: the card kicks a background refresh, and publishing it on
        # a public profile would expose data that `hide_github_activity` is
        # meant to withhold, an opt-out not yet wired up to rendering.
        # Omitted entirely without a linked account, so a profile with no data
        # stays the bio card alone.
        if is_owner:
            activity = github_activity_card_context(user)
            if activity["data"]["linked"]:
                context["github_activity"] = activity
        return context
