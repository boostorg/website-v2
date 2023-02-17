import pytest


@pytest.mark.skip("Reminder to write this test when I have the patience for mocks")
def test_import_social_profile_data():
    """
    TODO:
    - Test users.signals.import_social_profile_data
    - Set `SocialAccount.extra_data` to the github_api_get_user_by_username_response
      fixture in the libraries app -- it's not identical but it has what you need
    - You probably need to use `responses` and not `patch`
    """
    pass
