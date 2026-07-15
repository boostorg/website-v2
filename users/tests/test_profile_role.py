"""Tests for the displayed profile role feature (library-scoped roles)."""

import pytest
from model_bakery import baker

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from django.contrib.admin.sites import site

from users.admin import EmailUserAdmin, EmailUserAdminForm
from users.models import (
    ProfileRole,
    decode_role_option,
    encode_role_option,
)

User = get_user_model()


@pytest.fixture
def library(db):
    return baker.make("libraries.Library", name="Beast")


@pytest.fixture
def other_library(db):
    return baker.make("libraries.Library", name="Math")


def _make_version(library):
    version = baker.make("versions.Version")
    return baker.make("libraries.LibraryVersion", library=library, version=version)


def _add_commits(user, library, n):
    author = baker.make("libraries.CommitAuthor", name="Author", user=user)
    lv = _make_version(library)
    baker.make("libraries.Commit", author=author, library_version=lv, _quantity=n)


def _recompute():
    """Run the import-time recompute that populates resolved_profile_role.

    The auto-derived role is a snapshot maintained by this task, so tests that
    assert it must simulate the import having run.
    """
    from users.tasks import recompute_displayed_profile_roles

    recompute_displayed_profile_roles()


# --- option encoding helpers -------------------------------------------------


def test_encode_decode_roundtrip():
    assert encode_role_option("Author", 42) == "Author:42"
    assert decode_role_option("Author:42") == ("Author", 42)


def test_decode_empty_and_unscoped():
    assert decode_role_option("") == ("", None)
    assert decode_role_option("ceo:") == ("ceo", None)


# --- ProfileRole enum --------------------------------------------------------


def test_role_groups_are_disjoint():
    assert ProfileRole.library_roles() == {"Author", "Maintainer", "Contributor"}
    assert "ceo" in ProfileRole.internal_roles()
    assert not (ProfileRole.library_roles() & ProfileRole.internal_roles())


# --- eligibility (live per-user queries) ------------------------------------


def test_options_empty_for_user_without_contributions(user):
    assert user.get_role_library_options() == []
    assert user.role == ""


def test_author_option_and_scoped_label(user, library):
    library.authors.add(user)
    options = user.get_role_library_options()
    assert [(o["role"], o["library"].id) for o in options] == [("Author", library.id)]
    # No explicit choice -> default is the generic label for the top role.
    _recompute()
    assert User.objects.get(pk=user.pk).role == "Author"


def test_precedence_orders_author_before_maintainer(user, library, other_library):
    library.authors.add(user)
    _make_version(other_library).maintainers.add(user)
    roles = [o["role"] for o in user.get_role_library_options()]
    assert roles.index("Author") < roles.index("Maintainer")
    _recompute()
    assert User.objects.get(pk=user.pk).role == "Author"


def test_top_library_ranked_by_commit_count(user, library, other_library):
    library.authors.add(user)
    other_library.authors.add(user)
    _add_commits(user, other_library, 5)
    _add_commits(user, library, 1)
    # Commit count ranks the scoped options: the busier library comes first.
    libs = [o["library"].display_name for o in user.get_role_library_options()]
    assert libs.index("Boost.Math") < libs.index("Boost.Beast")
    # The default itself is the generic label.
    _recompute()
    assert User.objects.get(pk=user.pk).role == "Author"


def test_contributor_role_from_commits_only(user, library):
    _add_commits(user, library, 3)
    roles = [o["role"] for o in user.get_role_library_options()]
    assert roles == ["Contributor"]
    _recompute()
    assert User.objects.get(pk=user.pk).role == "Contributor"


# --- display composition -----------------------------------------------------


def test_explicit_library_scopes_the_role(user, library, other_library):
    library.authors.add(user)
    other_library.authors.add(user)
    user.displayed_profile_role = ProfileRole.AUTHOR.value
    user.displayed_profile_role_library = other_library
    user.save()
    assert User.objects.get(pk=user.pk).role == "Boost.Math Author"


def test_internal_title_renders_without_library(user):
    user.internal_role = ProfileRole.CEO.value
    user.save()
    assert user.role == "CEO, C++ Alliance"


def test_user_library_choice_wins_over_assigned_title(user, library):
    """A user's featured library role takes display precedence; the title
    (internal_role) is preserved as their default, not lost."""
    library.authors.add(user)
    user.internal_role = ProfileRole.CEO.value
    user.displayed_profile_role = ProfileRole.AUTHOR.value
    user.displayed_profile_role_library = library
    user.save()
    user = User.objects.get(pk=user.pk)
    assert user.role == "Boost.Beast Author"
    assert user.internal_role == ProfileRole.CEO.value  # not lost


def test_encoded_displayed_role_preselects_top_option(user, library):
    library.authors.add(user)
    _recompute()
    # Default preselects the generic option for the top role.
    assert User.objects.get(pk=user.pk).encoded_displayed_role == encode_role_option(
        "Author", ""
    )


def test_encoded_displayed_role_preselects_internal_title(user):
    user.internal_role = ProfileRole.CEO.value
    user.save()
    assert user.encoded_displayed_role == encode_role_option(ProfileRole.CEO.value, "")


def test_internal_title_is_first_and_default_option(user, library):
    """An assigned internal title heads the dropdown and is the default."""
    library.authors.add(user)  # also holds a library role
    user.internal_role = ProfileRole.CEO.value
    user.save()
    options = user.get_role_options()
    assert options[0] == {"role": ProfileRole.CEO.value, "library": None}
    # And it's the preselected value (no user library choice yet).
    assert user.encoded_displayed_role == encode_role_option(ProfileRole.CEO.value, "")


def test_dropdown_order_is_internal_then_generic_then_specific(
    user, library, other_library
):
    """Dropdown tiers, in order: internal title, generic labels, specific ones."""
    library.authors.add(user)
    other_library.authors.add(user)
    user.internal_role = ProfileRole.CEO.value
    user.save()
    options = user.get_role_options()
    # Tier 1: the internal title.
    assert options[0] == {"role": ProfileRole.CEO.value, "library": None}
    # Tier 2: generic (library-less) library roles.
    assert options[1] == {"role": "Author", "library": None}
    # Tier 3: specific library-scoped options, all after the generic ones.
    specific = [o for o in options if o["library"] is not None]
    first_specific = options.index(specific[0])
    assert all(o["library"] is None for o in options[:first_specific])


def test_selecting_title_clears_library_override(user, library, tp):
    """Selecting the assigned title clears the user's library-role override so
    the role falls back to the title (stored only in internal_role)."""
    library.authors.add(user)
    user.internal_role = ProfileRole.CEO.value
    user.displayed_profile_role = ProfileRole.AUTHOR.value
    user.displayed_profile_role_library = library
    user.save()
    value = encode_role_option(ProfileRole.CEO.value, "")
    with tp.login(user):
        tp.post(
            tp.reverse("profile-account"),
            data={"update_profile_role": "1", "role": value},
            follow=True,
        )
    user.refresh_from_db()
    assert user.displayed_profile_role == ""  # override cleared, not overwritten
    assert user.displayed_profile_role_library_id is None
    assert user.internal_role == ProfileRole.CEO.value
    assert user.role == "CEO, C++ Alliance"


def test_switching_to_library_role_keeps_title(user, library, tp):
    """The core of the split: featuring a library role never loses the title."""
    library.authors.add(user)
    user.internal_role = ProfileRole.CEO.value
    user.save()
    value = encode_role_option(ProfileRole.AUTHOR.value, library.id)
    with tp.login(user):
        tp.post(
            tp.reverse("profile-account"),
            data={"update_profile_role": "1", "role": value},
            follow=True,
        )
    user.refresh_from_db()
    assert user.displayed_profile_role == ProfileRole.AUTHOR.value
    assert user.internal_role == ProfileRole.CEO.value  # preserved
    assert user.role == "Boost.Beast Author"
    # The title is still offered first so the user can switch back.
    assert user.get_role_options()[0] == {
        "role": ProfileRole.CEO.value,
        "library": None,
    }


# --- generic (library-less) options ------------------------------------------


def test_generic_options_prepended_per_held_role(user, library, other_library):
    library.authors.add(user)
    _make_version(other_library).maintainers.add(user)
    options = user.get_role_options()
    # One generic (library=None) entry per held role, in precedence order, first.
    generic = [o for o in options if o["library"] is None]
    assert [o["role"] for o in generic] == ["Author", "Maintainer"]
    # Followed by the library-scoped options.
    assert all(o["library"] is not None for o in options[len(generic) :])


def test_generic_option_only_offered_for_held_roles(user, library):
    library.authors.add(user)  # Author only
    generic_roles = {o["role"] for o in user.get_role_options() if o["library"] is None}
    assert generic_roles == {"Author"}


def test_generic_role_renders_without_library(user, library):
    library.authors.add(user)
    user.displayed_profile_role = ProfileRole.AUTHOR.value
    user.displayed_profile_role_library = None
    user.save()
    assert User.objects.get(pk=user.pk).role == "Author"


def test_encoded_displayed_role_for_generic_selection(user, library):
    library.authors.add(user)
    user.displayed_profile_role = ProfileRole.AUTHOR.value
    user.displayed_profile_role_library = None
    user.save()
    assert user.encoded_displayed_role == encode_role_option("Author", "")


def test_post_persists_generic_role(user, library, tp):
    library.authors.add(user)
    value = encode_role_option(ProfileRole.AUTHOR.value, "")
    with tp.login(user):
        tp.post(
            tp.reverse("profile-account"),
            data={"update_profile_role": "1", "role": value},
            follow=True,
        )
    user.refresh_from_db()
    assert user.displayed_profile_role == ProfileRole.AUTHOR.value
    assert user.displayed_profile_role_library_id is None
    assert user.role == "Author"


# --- edit-page POST handler --------------------------------------------------


def test_post_persists_scoped_role(user, library, tp):
    library.authors.add(user)
    value = encode_role_option(ProfileRole.AUTHOR.value, library.id)
    with tp.login(user):
        tp.post(
            tp.reverse("profile-account"),
            data={"update_profile_role": "1", "role": value},
            follow=True,
        )
    user.refresh_from_db()
    assert user.displayed_profile_role == ProfileRole.AUTHOR.value
    assert user.displayed_profile_role_library_id == library.id
    assert user.role == "Boost.Beast Author"


def test_post_rejects_role_for_unheld_library(user, library, other_library, tp):
    library.authors.add(user)  # eligible for Beast only
    _recompute()  # populate the auto-derived fallback
    user.refresh_from_db()  # avoid clobbering resolved_profile_role on save
    user.displayed_profile_role = ProfileRole.AUTHOR.value
    user.displayed_profile_role_library = library
    user.save()
    tampered = encode_role_option(ProfileRole.AUTHOR.value, other_library.id)
    with tp.login(user):
        tp.post(
            tp.reverse("profile-account"),
            data={"update_profile_role": "1", "role": tampered},
            follow=True,
        )
    user.refresh_from_db()
    assert user.displayed_profile_role == ProfileRole.AUTHOR.value
    assert user.displayed_profile_role_library_id == library.id


def test_post_rejects_internal_title_from_user(user, library, tp):
    library.authors.add(user)
    _recompute()  # populate the auto-derived fallback
    user.refresh_from_db()  # avoid clobbering resolved_profile_role on save
    user.displayed_profile_role = ProfileRole.AUTHOR.value
    user.displayed_profile_role_library = library
    user.save()
    with tp.login(user):
        tp.post(
            tp.reverse("profile-account"),
            data={"update_profile_role": "1", "role": "ceo:"},
            follow=True,
        )
    user.refresh_from_db()
    assert user.displayed_profile_role == ProfileRole.AUTHOR.value
    assert user.displayed_profile_role_library_id == library.id


def test_post_empty_value_clears_selection(user, library, tp):
    library.authors.add(user)
    _recompute()  # populate the auto-derived fallback
    user.refresh_from_db()  # avoid clobbering resolved_profile_role on save
    user.displayed_profile_role = ProfileRole.AUTHOR.value
    user.displayed_profile_role_library = library
    user.save()
    with tp.login(user):
        tp.post(
            tp.reverse("profile-account"),
            data={"update_profile_role": "1", "role": ""},
            follow=True,
        )
    user.refresh_from_db()
    assert user.displayed_profile_role == ""
    assert user.displayed_profile_role_library_id is None
    # Falls back to the generic auto-picked derived role.
    assert user.role == "Author"


# --- single-holder internal titles -------------------------------------------


def test_singular_roles_subset():
    singular = set(ProfileRole.singular_roles())
    assert singular == {
        "ceo",
        "cfo_coo",
        "chief_of_staff",
        "cmo",
        "cto",
    }
    # All are internal, none are library roles.
    assert singular <= ProfileRole.internal_roles()


def test_db_blocks_second_holder_of_singular_title(db):
    baker.make(User, internal_role=ProfileRole.CEO.value)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            baker.make(User, internal_role=ProfileRole.CEO.value)


def test_full_clean_blocks_second_holder(db):
    baker.make(User, internal_role=ProfileRole.CEO.value)
    second = baker.make(User, internal_role="")
    second.internal_role = ProfileRole.CEO.value
    with pytest.raises(ValidationError):
        second.full_clean()


def test_multi_holder_titles_allow_duplicates(db):
    baker.make(User, internal_role=ProfileRole.BOARD_MEMBER.value)
    # No exception: multiple board members / software engineers are allowed.
    baker.make(User, internal_role=ProfileRole.BOARD_MEMBER.value)
    baker.make(User, internal_role=ProfileRole.SOFTWARE_ENGINEER.value)
    baker.make(User, internal_role=ProfileRole.SOFTWARE_ENGINEER.value)


def test_holder_can_resave_own_singular_title(db):
    holder = baker.make(User, internal_role=ProfileRole.CTO.value)
    holder.display_name = "Renamed"
    holder.full_clean()  # no false conflict against itself
    holder.save()
    holder.refresh_from_db()
    assert holder.display_name == "Renamed"


def test_admin_form_names_current_holder(db):
    holder = baker.make(
        User, display_name="Jane Doe", internal_role=ProfileRole.CEO.value
    )
    other = baker.make(User, internal_role="")
    form = EmailUserAdminForm(instance=other)
    form.cleaned_data = {"internal_role": ProfileRole.CEO.value}
    with pytest.raises(ValidationError) as exc:
        form.clean_internal_role()
    assert "Jane Doe" in str(exc.value)
    assert holder.display_name in str(exc.value)


def test_admin_form_allows_holder_to_keep_title(db):
    holder = baker.make(User, internal_role=ProfileRole.CEO.value)
    form = EmailUserAdminForm(instance=holder)
    form.cleaned_data = {"internal_role": ProfileRole.CEO.value}
    assert form.clean_internal_role() == ProfileRole.CEO.value


# --- admin: library roles derived/read-only, titles only ---------------------


def test_admin_form_offers_only_internal_titles(user):
    form = EmailUserAdminForm(instance=user)
    values = [c[0] for c in form.fields["internal_role"].choices]
    assert not any(v in ProfileRole.library_roles() for v in values)
    assert ProfileRole.CEO.value in values
    assert "" in values


def test_admin_derived_roles_display(user, library):
    library.authors.add(user)
    admin_obj = EmailUserAdmin(User, site)
    html = str(admin_obj.role_eligibility_display(user))
    assert "Author" in html
    assert "Beast" in html


# --- recompute task (auto-derived role snapshot) -----------------------------


def test_recompute_sets_highest_precedence_role(user, library, other_library):
    library.authors.add(user)  # Author
    _make_version(other_library).maintainers.add(user)  # + Maintainer
    _recompute()
    user.refresh_from_db()
    assert user.resolved_profile_role == ProfileRole.AUTHOR.value
    assert user.role == "Author"


def test_recompute_clears_role_when_no_longer_held(user, library):
    library.authors.add(user)
    _recompute()
    user.refresh_from_db()
    assert user.resolved_profile_role == ProfileRole.AUTHOR.value
    # Contribution revoked; the next import recompute blanks the derived role.
    library.authors.remove(user)
    _recompute()
    user.refresh_from_db()
    assert user.resolved_profile_role == ""
    assert user.role == ""


def test_recompute_clears_revoked_scoped_choice(user, library, other_library):
    """A user's explicit scoped choice is cleared once eligibility is revoked,
    so .role falls through instead of showing a role they no longer hold."""
    library.authors.add(user)
    other_library.authors.add(user)
    user.displayed_profile_role = ProfileRole.AUTHOR.value
    user.displayed_profile_role_library = library
    user.save()
    # Still an author of Beast -> choice survives the recompute.
    _recompute()
    user.refresh_from_db()
    assert user.displayed_profile_role == ProfileRole.AUTHOR.value
    # Remove Beast authorship: the specific choice is now invalid.
    library.authors.remove(user)
    _recompute()
    user.refresh_from_db()
    assert user.displayed_profile_role == ""
    assert user.displayed_profile_role_library_id is None
    # Falls through to the derived role (still an author of Math).
    assert user.role == "Author"


def test_recompute_clears_revoked_generic_choice(user, library):
    """A generic choice (no library) is cleared when the role is held nowhere."""
    library.authors.add(user)
    user.displayed_profile_role = ProfileRole.AUTHOR.value
    user.displayed_profile_role_library = None
    user.save()
    library.authors.remove(user)  # no longer an author of any library
    _recompute()
    user.refresh_from_db()
    assert user.displayed_profile_role == ""
    assert user.role == ""
