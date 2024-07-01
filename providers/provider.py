from allauth.socialaccount import providers
from allauth.socialaccount.providers.base import ProviderAccount
from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider


class BoostAccount(ProviderAccount):
    pass


class BoostProvider(OAuth2Provider):
    id = "provider"
    name = "Boost OAuth2 Provider"
    account_class = BoostAccount

    def extract_uid(self, data):
        return str(data["id"])

    def extract_common_fields(self, data):
        return {
            dict(
                email="testing@testing.com",
                first_name="Tester",
                last_name="Testerson",
            )
        }


providers.registry.register(BoostProvider)
