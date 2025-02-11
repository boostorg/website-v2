from django.db import models
from django.db.models.fields.files import FieldFile


class NullableFileField(models.FileField):
    def get_db_prep_value(self, value, connection, prepared=False):
        if isinstance(value, FieldFile):
            if not value.name:
                return None
            value = value.name
        return super().get_db_prep_value(value, connection, prepared)
