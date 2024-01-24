import requests
from allauth.socialaccount.providers.oauth2.views import (
    OAuth2Adapter,
    OAuth2LoginView,
    OAuth2CallbackView,
)
from .provider import BoostProvider
from django.conf import settings


class CustomAdapter(OAuth2Adapter):
    provider_id = BoostProvider.id

    access_token_url = f"{settings.OAUTH_SERVER_BASEURL}/oauth2/token/"
    profile_url = f"{settings.OAUTH_SERVER_BASEURL}/api/v1/users/me/"

    authorize_url = f"{settings.OAUTH_SERVER_BASEURL}/oauth2/authorize/"

    def dispatch(self, request, *args, **kwargs):
        print("In the dispatch")
        return super().dispatch(request, *args, **kwargs)

    def complete_login(self, request, app, token, **kwargs):
        print("in the complete login method")
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Accept": "application/json",
        }
        kwargs["response"]["email"]
        resp = requests.get(self.profile_url, headers=headers)
        resp.raise_for_status()
        print(resp.status_code)
        extra_data = resp.json()
        return self.get_provider().sociallogin_from_response(request, extra_data)


oauth2_login = OAuth2LoginView.adapter_view(CustomAdapter)
oauth2_callback = OAuth2CallbackView.adapter_view(CustomAdapter)
