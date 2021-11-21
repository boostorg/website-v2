from django.db import transaction
from django.db import IntegrityError
import tempfile
from django.urls import reverse
from rest_framework.test import APIClient
from test_plus.test import TestCase

from users.factories import UserFactory, SuperUserFactory, VersionGroupFactory
from versions.factories import VersionFactory

from PIL import Image


class VersionViewTests(TestCase):
    client_class = APIClient

    def setUp(self):
        self.user = UserFactory()
        self.group_user = UserFactory.create(groups=(VersionGroupFactory.create(),))
        self.super_user = SuperUserFactory()
        self.version_manager = UserFactory()
        self.version = VersionFactory()

    def test_list_version(self):
        """
        Tests with a regular user
        """
        # Does API work without auth?
        response = self.get("versions-list")
        self.response_403(response)

        # Does API work with auth?
        with self.login(self.user):
            response = self.get("versions-list")
            self.response_200(response)
            self.assertEqual(len(response.data), 1)
            # Are non-staff shown/hidden the right fields?
            self.assertIn("name", response.data[0])
            self.assertIn("checksum", response.data[0])

    def test_create(self):
        image = Image.new("RGB", (100, 100))

        tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg")
        image.save(tmp_file)

        tmp_file.seek(0)

        payload = {
            "file": tmp_file,
            "name": "First Version",
            "release_date": "2021-01-01",
        }

        # Does API work without auth?
        response = self.client.post(
            reverse("versions-list"), files=payload, format="multipart"
        )
        self.response_403(response)

        tmp_file.seek(0)
        # Does API work with normal user?
        with self.login(self.user):
            response = self.client.post(
                reverse("versions-list"), data=payload, format="multipart"
            )
            self.response_403(response)

        tmp_file.seek(0)
        # Does API work with super user?
        with self.login(self.super_user):
            try:
                with transaction.atomic():
                    response = self.client.post(
                        reverse("versions-list"), data=payload, format="multipart"
                    )
                    self.response_201(response)
            except IntegrityError:
                pass

        tmp_file.seek(0)
        # Does API work with version_manager user?
        with self.login(self.group_user):
            try:
                with transaction.atomic():
                    response = self.client.post(
                        reverse("versions-list"), data=payload, format="multipart"
                    )
                    self.response_201(response)
            except IntegrityError:
                pass

    def test_delete(self):
        url = reverse("versions-detail", kwargs={"pk": self.version.pk})

        # Does this API work without auth?
        response = self.client.delete(url, format="json")
        self.response_403(response)

        # Does this API wotk with non-staff user?
        with self.login(self.user):
            response = self.client.delete(url, format="json")
            self.response_403(response)

        # Does this API work with super user?
        with self.login(self.super_user):
            response = self.client.delete(url, format="json")
            self.assertEqual(response.status_code, 204)

            # Confirm object is gone
            response = self.get(url)
            self.response_404(response)

    def test_update(self):
        old_name = self.version.name
        url = reverse("versions-detail", kwargs={"pk": self.version.pk})

        image = Image.new("RGB", (100, 100))

        tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg")
        image.save(tmp_file)

        tmp_file.seek(0)

        payload = {"file": tmp_file, "name": "Second Version"}

        # Does API work without auth?
        response = self.client.post(url, files=payload, format="multipart")
        self.response_403(response)

        tmp_file.seek(0)
        # Does API work with normal user?
        with self.login(self.user):
            response = self.client.patch(url, data=payload, format="multipart")
            self.response_403(response)

        tmp_file.seek(0)
        # Does API work with super user?
        with self.login(self.super_user):
            try:
                with transaction.atomic():
                    response = self.client.patch(url, data=payload, format="multipart")
                    self.response_200(response)
                    self.assertNotEqual(old_name, response.data["name"])
            except IntegrityError:
                pass

        tmp_file.seek(0)
        # Does API work with version_manager user?
        with self.login(self.group_user):
            try:
                with transaction.atomic():
                    response = self.client.patch(url, data=payload, format="multipart")
                    self.response_200(response)
                    self.assertNotEqual(old_name, response.data["name"])
            except IntegrityError:
                pass
