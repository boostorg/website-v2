import django_filters as filters

from .models import Category, Library
from versions.models import Version


class LibraryFilter(filters.FilterSet):
    category = filters.CharFilter(field_name="categories__slug")
    version = filters.CharFilter(field_name="versions__slug")

    class Meta:
        model = Library
        fields = ["category", "version"]
