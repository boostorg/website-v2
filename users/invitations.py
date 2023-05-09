from .models import InvitationToken


def generate_invitation_token(user):
    token = InvitationToken.objects.create(user=user)
    return token