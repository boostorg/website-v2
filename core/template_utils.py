class InvalidTemplateVariable(str):
    def __mod__(self, other):
        from django.conf import settings

        if settings.DEBUG:
            # Revert from crashing to providing a visible marker
            return f"INVALID_VARIABLE_{other}"
        return ""

    def __repr__(self):
        return f"InvalidTemplateVariable('{self}')"

    def __str__(self):
        return f"Invalid template variable: {self}"
