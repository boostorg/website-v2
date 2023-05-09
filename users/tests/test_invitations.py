import datetime
from django.core import mail
from django.urls import reverse
from users.models import InvitationToken
from users.invitations import generate_invitation_token


def test_generate_invitation_token(user):
    token = generate_invitation_token(user)
    assert isinstance(token, InvitationToken)
    assert token.user == user
