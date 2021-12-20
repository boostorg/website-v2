from django.db import transaction
from django.db import IntegrityError
from django.core.files import File as DjangoFile

import tempfile
from django.urls import reverse
from rest_framework.test import APIClient
from test_plus.test import TestCase

from users.factories import UserFactory, SuperUserFactory, VersionGroupFactory
from versions.factories import VersionFactory, VersionFileFactory

from PIL import Image

from versions.models import VersionFile


class VersionViewTests(TestCase):
    client_class = APIClient

    def setUp(self):
        self.user = UserFactory()
        self.group_user = UserFactory.create(groups=(VersionGroupFactory.create(),))
        self.super_user = SuperUserFactory()
        self.version_manager = UserFactory()
        self.version_file1 = VersionFileFactory()
        self.version_file2 = VersionFileFactory()
        self.version = VersionFactory.create(
            files=(self.version_file1, self.version_file2)
        )

    def test_list_version(self):
        """
        Tests with a regular user
        """
        # Does API work without auth?
        response = self.get("version-files-list")
        self.response_403(response)

        # Does API work with auth?
        with self.login(self.user):
            response = self.get("version-files-list")
            self.response_200(response)
            self.assertEqual(len(response.data), 2)
            self.assertIn("checksum", response.data[0])
            self.assertIn("operating_system", response.data[0])

    def test_create(self):
        image = Image.new("RGB", (100, 100))

        tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg")
        image.save(tmp_file)

        tmp_file.seek(0)
        file_obj = DjangoFile(open(tmp_file.name, mode="rb"), name="tmp_file")

        payload = {"file": file_obj, "operating_system": "Windows"}

        #Does API work without auth?
        response = self.client.post(
            reverse("version-files-list"), files=payload, format="multipart"
        )
        self.response_403(response)

        file_obj.seek(0)
        # Does API work with normal user?
        with self.login(self.user):
            response = self.client.post(
                reverse("version-files-list"), data=payload, format="multipart"
            )
            self.response_403(response)

        file_obj.seek(0)
        # # Does API work with super user?
        with self.login(self.super_user):
            try:
                with transaction.atomic():
                    response = self.client.post(
                        reverse("version-files-list"), data=payload, format="multipart"
                    )
                    self.response_201(response)
            except IntegrityError:
                pass

        file_obj.seek(0)
        # Does API work with version_manager user?
        with self.login(self.group_user):
            try:
                with transaction.atomic():
                    response = self.client.post(
                        reverse("version-files-list"), data=payload, format="multipart"
                    )
                    self.response_201(response)
            except IntegrityError:
                pass
    
    def test_delete(self):
        url = reverse("version-files-detail", kwargs={"pk": self.version_file1.pk})

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
        url = reverse("version-files-detail", kwargs={"pk": self.version_file2.pk})

        image = Image.new("RGB", (100, 100))

        tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg")
        image.save(tmp_file)

        tmp_file.seek(0)
        file_obj = DjangoFile(open(tmp_file.name, mode='rb'), name="tmp_file")

        file_obj.seek(0)

        payload = {
            "file": file_obj,
        }

        # Does API work without auth?
        response = self.client.post(url, files=payload, format="multipart")
        self.response_403(response)

        file_obj.seek(0)
        # Does API work with normal user?
        with self.login(self.user):
            response = self.client.patch(url, data=payload, format="multipart")
            self.response_403(response)

        file_obj.seek(0)
        # Does API work with super user?
        with self.login(self.super_user):
            try:
                with transaction.atomic():
                    response = self.client.patch(url, data=payload, format="multipart")
                    self.response_200(response)
            except IntegrityError:
                pass

        file_obj.seek(0)
        # Does API work with version_manager user?
        with self.login(self.group_user):
            try:
                with transaction.atomic():
                    response = self.client.patch(url, data=payload, format="multipart")
                    self.response_200(response)
            except IntegrityError:
                pass
