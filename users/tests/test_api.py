from django.urls import reverse
from faker import Faker
from rest_framework.test import APIClient
from test_plus.test import TestCase

from ..factories import UserFactory, StaffUserFactory
from .. import serializers


class UserViewTests(TestCase):
    client_class = APIClient

    def setUp(self):
        self.user = UserFactory()
        self.staff = StaffUserFactory()
        self.sample_user = UserFactory()

    def test_list_user(self):
        """
        Tests with a regular user
        """
        # Does API work without auth?
        response = self.get("users-list")
        self.response_403(response)

        # Does API work with auth?
        with self.login(self.user):
            response = self.get("users-list")
            self.response_200(response)
            self.assertEqual(len(response.data), 3)
            # Are non-staff shown/hidden the right fields?
            self.assertIn("first_name", response.data[0])
            self.assertNotIn("date_joined", response.data[0])

    def test_list_staff(self):
        """
        Test with a staff user, who use a different serializer
        """
        # Are staff shown the right fields?
        with self.login(self.staff):
            response = self.get("users-list")
            self.response_200(response)
            self.assertEqual(len(response.data), 3)
            self.assertIn("first_name", response.data[0])
            self.assertIn("date_joined", response.data[0])

    def test_detail(self):
        # Does this API work without auth?
        response = self.get("users-detail", pk=self.sample_user.pk)
        self.response_403(response)

        # Does this API work with non-staff auth?
        with self.login(self.user):
            response = self.get("users-detail", pk=self.sample_user.pk)
            self.response_200(response)
            self.assertIn("first_name", response.data)
            self.assertNotIn("date_joined", response.data)

        # Does this API work with staff auth?
        with self.login(self.staff):
            response = self.get("users-detail", pk=self.sample_user.pk)
            self.response_200(response)
            self.assertIn("first_name", response.data)
            self.assertIn("date_joined", response.data)

    def test_create(self):
        user = UserFactory.build()
        payload = serializers.FullUserSerializer(user).data

        # Does API work without auth?
        response = self.client.post(reverse("users-list"), data=payload, format="json")
        self.response_403(response)

        # Does API work with non-staff user?
        with self.login(self.user):
            response = self.client.post(
                reverse("users-list"), data=payload, format="json"
            )
            self.response_403(response)

        # Does API work with staff user?
        with self.login(self.staff):
            response = self.client.post(
                reverse("users-list"), data=payload, format="json"
            )
            self.response_201(response)

    def test_delete(self):
        url = reverse("users-detail", kwargs={"pk": self.sample_user.pk})

        # Does this API work without auth?
        response = self.client.delete(url, format="json")
        self.response_403(response)

        # Does this API wotk with non-staff user?
        with self.login(self.user):
            response = self.client.delete(url, format="json")
            self.response_403(response)

        # Does this API work with staff user?
        with self.login(self.staff):
            response = self.client.delete(url, format="json")
            self.assertEqual(response.status_code, 204)

            # Confirm object is gone
            response = self.get(url)
            self.response_404(response)

    def test_update(self):
        url = reverse("users-detail", kwargs={"pk": self.sample_user.pk})

        old_name = self.sample_user.first_name
        payload = serializers.FullUserSerializer(self.sample_user).data

        # Does this API work without auth?
        response = self.client.put(url, payload, format="json")
        self.response_403(response)

        # Does this API work with non-staff auth?
        with self.login(self.user):
            self.sample_user.first_name = Faker().name()
            payload = serializers.FullUserSerializer(self.sample_user).data
            response = self.client.put(url, payload, format="json")
            self.response_403(response)

        # Does this APO work with staff auth?
        with self.login(self.staff):
            self.sample_user.first_name = Faker().name()
            payload = serializers.FullUserSerializer(self.sample_user).data
            response = self.client.put(url, payload, format="json")
            self.response_200(response)
            self.assertFalse(response.data["first_name"] == old_name)

            # Test updating reversions
            self.sample_user.first_name = old_name
            payload = serializers.FullUserSerializer(self.sample_user).data
            response = self.client.put(url, payload, format="json")
            self.assertTrue(response.data["first_name"] == old_name)


class CurrentUserViewTests(TestCase):
    client_class = APIClient

    def setUp(self):
        self.user = UserFactory()
        self.staff = StaffUserFactory()

    def test_get_current_user(self):
        # Does this API work without auth?
        response = self.get("current-user")
        self.response_403(response)

        # Does this API work with auth?
        with self.login(self.user):
            response = self.get("current-user")
            self.response_200(response)
            self.assertIn("first_name", response.data)
            self.assertIn("date_joined", response.data)

    def test_create(self):
        user = UserFactory.build()
        payload = serializers.CurrentUserSerializer(user).data

        # Does API work without auth?
        response = self.client.post(
            reverse("current-user"), data=payload, format="json"
        )
        self.response_403(response)

        # Does API work with non-staff user?
        with self.login(self.user):
            response = self.client.post(
                reverse("current-user"), data=payload, format="json"
            )
            self.response_405(response)

        # Does API work with staff user?
        with self.login(self.staff):
            response = self.client.post(
                reverse("current-user"), data=payload, format="json"
            )
            self.response_405(response)

    def test_update(self):
        old_name = self.user.first_name
        payload = serializers.CurrentUserSerializer(self.user).data

        # Does this API work without auth?
        response = self.client.post(
            reverse("current-user"), data=payload, format="json"
        )
        self.response_403(response)

        # Does this API work with auth?
        with self.login(self.user):
            self.user.first_name = Faker().name()
            payload = serializers.CurrentUserSerializer(self.user).data
            response = self.client.put(reverse("current-user"), payload, format="json")
            self.response_200(response)
            self.assertFalse(response.data["first_name"] == old_name)

            # Test updating reversions
            self.user.first_name = old_name
            payload = serializers.CurrentUserSerializer(self.user).data
            response = self.client.put(reverse("current-user"), payload, format="json")
            self.assertTrue(response.data["first_name"] == old_name)

        # Can user update readonly fields?
        old_email = self.user.email

        with self.login(self.user):
            self.user.email = Faker().email()
            payload = serializers.CurrentUserSerializer(self.user).data
            response = self.client.put(reverse("current-user"), payload, format="json")
            self.response_200(response)
            self.assertEqual(response.data["email"], old_email)

    def test_delete(self):
        # Does this API work without auth?
        response = self.client.delete(reverse("current-user"), format="json")
        self.response_403(response)

        # Does this API wotk with auth? Should not.
        with self.login(self.user):
            response = self.client.delete(reverse("current-user"), format="json")
            self.response_405(response)
