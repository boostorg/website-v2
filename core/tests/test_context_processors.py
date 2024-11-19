from core.context_processors import current_version


def test_current_version_context(
    version, beta_version, inactive_version, old_version, rf
):
    """Test the current_version context processor. Making the other versions
    ensures that the most_recent() method returns the correct version."""
    request = rf.get("/")
    context = current_version(request)
    assert "current_version" in context
    assert context["current_version"] == version
