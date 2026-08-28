from datetime import datetime

import pytest
from django.utils import timezone

from contributions.models import Email, GitProfile, GitContribution, Identity
from contributions.parsers.git_repositories import (
    parsed_commit_to_git_contribution,
)
from libraries.github import ParsedCommit
from libraries.models import Library


@pytest.fixture
def library():
    """Create a test library."""
    return Library.objects.create(
        key="beast", name="Beast", github_url="https://github.com/boostorg/beast"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "email,name,sha,message,library_key",
    [
        ("john@example.com", "John Doe", "abc123def456", "Fix bug in parser", "beast"),
        ("jane@example.com", "Jane Smith", "789xyz012", "Add new feature", "system"),
    ],
)
def test_parsed_commit_to_git_contribution(
    library, email, name, sha, message, library_key
):
    """Test converting ParsedCommit to GitContribution."""
    committed_at = timezone.make_aware(datetime(2024, 1, 15, 10, 30, 0))

    parsed_commit = ParsedCommit(
        email=email,
        name=name,
        message=message,
        sha=sha,
        version="boost-1.86.0",
        is_merge=False,
        committed_at=committed_at,
        avatar_url="https://example.com/avatar.jpg",
    )

    contribution = parsed_commit_to_git_contribution(
        parsed_commit, library_key, library.id
    )

    # Verify Email was created
    assert Email.objects.filter(email=email).exists()
    email_obj = Email.objects.get(email=email)

    # Verify GitProfile was created
    assert GitProfile.objects.filter(email=email_obj).exists()
    git_profile = GitProfile.objects.get(email=email_obj)
    assert git_profile.name == name  # Should use actual commit author name

    # Verify GitContribution structure
    assert isinstance(contribution, GitContribution)
    assert contribution.profile == git_profile
    assert contribution.contributed_at == committed_at
    assert contribution.repo == library_key
    assert contribution.info == sha
    assert contribution.comment == message


@pytest.mark.django_db
def test_parsed_commit_to_git_contribution_reuses_existing_email(library):
    """Test that parsed_commit_to_git_contribution reuses existing Email."""
    email = "existing@example.com"

    # Create existing email
    existing_email = Email.objects.create(email=email)

    parsed_commit = ParsedCommit(
        email=email,
        name="Test User",
        message="Test commit",
        sha="abc123",
        version="boost-1.86.0",
        is_merge=False,
        committed_at=timezone.now(),
    )

    contribution = parsed_commit_to_git_contribution(parsed_commit, "beast", library.id)

    # Should only have one Email object
    assert Email.objects.filter(email=email).count() == 1
    assert contribution.profile.email == existing_email


@pytest.mark.django_db
def test_parsed_commit_to_git_contribution_reuses_existing_profile(library):
    """Test that parsed_commit_to_git_contribution reuses and updates existing GitProfile."""
    email = "existing@example.com"

    # Create existing email and profile
    existing_email = Email.objects.create(email=email)
    existing_profile = GitProfile.objects.create(
        email=existing_email, name="Original Name"
    )

    parsed_commit = ParsedCommit(
        email=email,
        name="Different Name",
        message="Test commit",
        sha="abc123",
        version="boost-1.86.0",
        is_merge=False,
        committed_at=timezone.now(),
    )

    contribution = parsed_commit_to_git_contribution(parsed_commit, "beast", library.id)

    # Should reuse existing profile (same pk)
    assert GitProfile.objects.filter(email=existing_email).count() == 1
    assert contribution.profile.pk == existing_profile.pk
    # Name should be updated to actual commit author name
    existing_profile.refresh_from_db()
    assert existing_profile.name == "Different Name"


@pytest.mark.django_db
def test_parsed_commit_to_git_contribution_handles_merge_commit(library):
    """Test that parsed_commit_to_git_contribution handles merge commits."""
    parsed_commit = ParsedCommit(
        email="merger@example.com",
        name="Merger User",
        message="Merge branch 'feature' into develop",
        sha="merge123",
        version="boost-1.86.0",
        is_merge=True,  # This is a merge commit
        committed_at=timezone.now(),
    )

    contribution = parsed_commit_to_git_contribution(parsed_commit, "beast", library.id)

    # Should still create the contribution (merge commits are tracked)
    assert isinstance(contribution, GitContribution)
    assert contribution.comment == "Merge branch 'feature' into develop"


@pytest.mark.django_db
def test_parsed_commit_to_git_contribution_contribution_not_saved(library):
    """Test that parsed_commit_to_git_contribution returns unsaved contribution."""
    parsed_commit = ParsedCommit(
        email="test@example.com",
        name="Test User",
        message="Test commit",
        sha="abc123",
        version="boost-1.86.0",
        is_merge=False,
        committed_at=timezone.now(),
    )

    contribution = parsed_commit_to_git_contribution(parsed_commit, "beast", library.id)

    # Contribution should not be saved to database yet
    assert contribution.pk is None
    assert not GitContribution.objects.filter(info="abc123").exists()

    # Save it to verify it works
    contribution.save()
    assert contribution.pk is not None
    assert GitContribution.objects.filter(info="abc123").exists()


@pytest.mark.django_db
def test_parsed_commit_to_git_contribution_multiple_commits_same_author(library):
    """Test that multiple commits from same author reuse the same profile."""
    email = "author@example.com"
    library_key = "beast"

    commit1 = ParsedCommit(
        email=email,
        name="Author Name",
        message="First commit",
        sha="sha1",
        version="boost-1.86.0",
        is_merge=False,
        committed_at=timezone.now(),
    )

    commit2 = ParsedCommit(
        email=email,
        name="Author Name",
        message="Second commit",
        sha="sha2",
        version="boost-1.86.0",
        is_merge=False,
        committed_at=timezone.now(),
    )

    contribution1 = parsed_commit_to_git_contribution(commit1, library_key, library.id)
    contribution2 = parsed_commit_to_git_contribution(commit2, library_key, library.id)

    # Should reuse the same email and profile
    assert Email.objects.filter(email=email).count() == 1
    assert GitProfile.objects.filter(email__email=email).count() == 1
    assert contribution1.profile == contribution2.profile


@pytest.mark.django_db
def test_parsed_commit_to_git_contribution_uses_commit_author_name(library):
    """Test that profile name uses actual commit author name."""
    email = "john.doe@example.com"

    parsed_commit = ParsedCommit(
        email=email,
        name="John Doe Full Name",
        message="Test commit",
        sha="abc123",
        version="boost-1.86.0",
        is_merge=False,
        committed_at=timezone.now(),
    )

    contribution = parsed_commit_to_git_contribution(parsed_commit, "beast", library.id)

    # Profile name should use the actual commit author name
    assert contribution.profile.name == "John Doe Full Name"


@pytest.mark.django_db
def test_parsed_commit_to_git_contribution_creates_identity_for_new_profile(library):
    """Test that an Identity is created when a new GitProfile is created."""
    email = "newuser@example.com"

    parsed_commit = ParsedCommit(
        email=email,
        name="New User",
        message="Test commit",
        sha="abc123",
        version="boost-1.86.0",
        is_merge=False,
        committed_at=timezone.now(),
    )

    contribution = parsed_commit_to_git_contribution(parsed_commit, "beast", library.id)

    # Verify GitProfile was created and has an identity
    git_profile = contribution.profile
    assert git_profile.identity is not None
    assert isinstance(git_profile.identity, Identity)
    assert git_profile.identity.name == "New User"  # Uses actual commit author name


@pytest.mark.django_db
def test_parsed_commit_to_git_contribution_does_not_create_identity_for_existing_profile(
    library,
):
    """Test that an Identity is not created when reusing an existing GitProfile."""
    email = "existing@example.com"

    # Create existing email and profile with identity
    existing_email = Email.objects.create(email=email)
    existing_identity = Identity.objects.create(name="Existing Identity")
    existing_profile = GitProfile.objects.create(
        email=existing_email, name="existing", identity=existing_identity
    )

    initial_identity_count = Identity.objects.count()

    parsed_commit = ParsedCommit(
        email=email,
        name="New Name",
        message="Test commit",
        sha="abc123",
        version="boost-1.86.0",
        is_merge=False,
        committed_at=timezone.now(),
    )

    parsed_commit_to_git_contribution(parsed_commit, "beast", library.id)

    # Should not create a new identity
    assert Identity.objects.count() == initial_identity_count
    # Should keep the existing identity
    existing_profile.refresh_from_db()
    assert existing_profile.identity == existing_identity


@pytest.mark.django_db
def test_parsed_commit_to_git_contribution_fallback_to_email_username(library):
    """Test that profile name falls back to email username when commit author name is empty."""
    email = "fallback@example.com"

    parsed_commit = ParsedCommit(
        email=email,
        name="",  # Empty name
        message="Test commit",
        sha="abc123",
        version="boost-1.86.0",
        is_merge=False,
        committed_at=timezone.now(),
    )

    contribution = parsed_commit_to_git_contribution(parsed_commit, "beast", library.id)

    # Profile name should fall back to email username
    assert contribution.profile.name == "fallback"


@pytest.mark.django_db
def test_parsed_commit_to_git_contribution_fallback_to_email_username_when_none(
    library,
):
    """Test that profile name falls back to email username when commit author name is None."""
    email = "fallback2@example.com"

    parsed_commit = ParsedCommit(
        email=email,
        name=None,  # None name
        message="Test commit",
        sha="abc123",
        version="boost-1.86.0",
        is_merge=False,
        committed_at=timezone.now(),
    )

    contribution = parsed_commit_to_git_contribution(parsed_commit, "beast", library.id)

    # Profile name should fall back to email username
    assert contribution.profile.name == "fallback2"
