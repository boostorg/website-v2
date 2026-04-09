from django.conf import settings


def build_password_rules():
    """Generate frontend password rules from AUTH_PASSWORD_VALIDATORS.

    Each Django validator maps to one or more frontend rule dicts consumed
    by the Alpine.js checklist in _field_password.html.
    """
    rules = []
    for validator in settings.AUTH_PASSWORD_VALIDATORS:
        name = validator["NAME"].rsplit(".", 1)[-1]
        options = validator.get("OPTIONS", {})

        if name == "MinimumLengthValidator":
            min_len = options.get("min_length", 9)
            rules.append(
                {
                    "label": f"At least {min_len} characters",
                    "type": "min_length",
                    "value": min_len,
                }
            )
        elif name == "NumericPasswordValidator":
            rules.append(
                {
                    "label": "Can't be entirely numeric",
                    "type": "regex",
                    "value": "[^0-9]",
                }
            )
        elif name == "UserAttributeSimilarityValidator":
            rules.append(
                {
                    "label": "Does not contain your email address",
                    "type": "not_contains_field",
                    "value": "#field-email",
                }
            )
            rules.append(
                {
                    "label": "Does not contain your username",
                    "type": "not_contains_field",
                    "value": "#field-username",
                }
            )
        elif name == "CommonPasswordValidator":
            rules.append({"label": "Is not commonly used", "type": "server_only"})

    return rules
