from core.context_processors import current_release


def test_current_release_context(
    version, beta_version, inactive_version, old_version, rf
):
    """Test the current_release context processor. Making the other versions
    ensures that the most_recent() method returns the correct version."""
    request = rf.get("/")
    context = current_release(request)
    assert "current_release" in context
    assert context["current_release"] == version
