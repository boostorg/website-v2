from urllib.parse import urlparse

from badges import display as badge_display
from badges.summary import user_badge_summary
from core.context_processors import edit_profile_url
from users.profile_cards import github_activity_card_context


class V3UserProfileContextMixin:
    """Read-only v3 profile context, shared by the public profile page and by
    the logged-in user's own (non-editable) view of their profile.

    Both pages render `v3/user_profile_page.html` from the same data. They
    differ only in the buttons trailing the profile links: everyone gets Share
    Profile, the profile's owner also gets Edit Profile ahead of it (see
    `get_trailing_buttons()`), and only the owner's view carries the account
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

    def get_trailing_buttons(self, user):
        """The header buttons that follow the profile links.

        Everyone can share a profile, so Share Profile comes last for owner and
        visitor alike. Owners additionally get Edit Profile ahead of it, on both
        `/users/me/` and their own `/users/<routing-key>/` page, so the
        affordance follows who is looking rather than which route was used."""
        buttons = []
        if user == self.request.user:
            buttons.append(
                {
                    "label": "Edit Profile",
                    "url": edit_profile_url(),
                    "icon": "pixel-pencil",
                }
            )
        # A real href rather than "#": share-profile.js copies it to the
        # clipboard, and with JS off the button still leads somewhere sensible.
        buttons.append(
            {
                "label": "Share Profile",
                "url": user.get_absolute_url(),
                "icon": "pixel-share",
                "extra_classes": "js-copy-profile-url",
            }
        )
        return buttons

    def get_v3_profile_link_buttons(self, user):
        """Header buttons for the public profile links the user has set.

        Links with no (or an unsafe) value are omitted, since only populated
        links are shown publicly. The list always ends with the trailing
        buttons."""
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
        buttons.extend(self.get_trailing_buttons(user))
        return buttons

    def get_v3_public_context(self, user):
        """Context for the read-only v3 profile view.

        Renders real user data. Sections with no underlying data (GitHub
        activity, mailing list activity, posts) are left out of the context so
        the template omits them entirely; achievements are present but empty,
        which the template treats the same way. The bio section is always
        rendered, falling back to an empty state."""
        is_owner = user == self.request.user
        # Read once and used twice below: the achievements card and the
        # dialog's counters are the same query. Both readers live here so that
        # every route to a page gets the same answer for the same cost.
        summary_rows = user_badge_summary(user)
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
                **user.profile_stamps,
                # include_hidden only for the owner, for the same reason as
                # `role`: a member who hid their badges still sees them on
                # their own page, and a visitor never does.
                "featured_badge": badge_display.featured_badge(
                    user, include_hidden=is_owner
                ),
            },
            "profile_badges": badge_display.badge_cards(user, include_hidden=is_owner),
            # Dict-wrapped to match the shape the v3 component gallery feeds
            # the same card. Empty for a member who has earned nothing, and the
            # card is then left out rather than shown as an example.
            "achievements_data": {
                "achievements": badge_display.achievement_cards(user, rows=summary_rows)
            },
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
        # Owner-only, and keyed on who is looking rather than which URL was
        # used: `/users/me/` and your own `/users/<routing-key>/` page are the
        # same page, so both show your real tallies. A visitor gets no rows at
        # all and the dialog falls back to the catalogue, another member's
        # tallies not being this dialog's to show.
        if is_owner:
            context["achievement_dialog_items"] = badge_display.achievement_dialog_rows(
                user, rows=summary_rows
            )
        # Rendered on anyone's profile, not just your own, and omitted entirely
        # without a linked GitHub account so a profile with no data stays the
        # bio card alone. include_hidden for the owner, for the same reason as
        # `role` and the badges above: a member who hid their activity still
        # sees it on their own page, and a visitor never does.
        activity = github_activity_card_context(user, include_hidden=is_owner)
        if activity and activity["data"]["linked"]:
            context["github_activity"] = activity
        return context
