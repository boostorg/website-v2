from unittest.mock import patch
from django.contrib.auth import get_user_model


User = get_user_model()


def test_public_view(full_version_one, tp):
    r = tp.client.get("/api/v1/versions/")
    tp.response_200(r)


def test_import_versions_view(user, staff_user, tp):
    """
    POST /api/v1/import-versions/
    """
    with patch("versions.tasks.import_versions.delay") as mock_task, tp.login(
        staff_user
    ):
        response = tp.post("import-versions")
        mock_task.assert_called_once()
        tp.response_200(response)

    with patch("versions.tasks.import_versions.delay") as mock_task, tp.login(user):
        response = tp.post("import-versions")
        mock_task.assert_not_called()
        tp.response_302(response)
