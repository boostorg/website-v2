from django.db.models import Q

from rest_framework import permissions
from rest_framework import viewsets
from rest_framework import serializers
from rest_framework import renderers
from rest_framework.response import Response

from .models import Library


class LibrarySearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Library
        fields = (
            "name",
            "description",
            "slug",
        )


class LibrarySearchView(viewsets.ModelViewSet):
    model = Library
    serializer_class = LibrarySearchSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Library.objects.all()
    renderer_classes = (renderers.TemplateHTMLRenderer,)

    def filter_queryset(self, queryset):
        """
        This view should return a list of all the libraries that
        match the search params limited to 5 results
        """
        value = self.request.query_params.get("q")
        f = (
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(categories__name__icontains=value)
            | Q(authors__first_name__icontains=value)
            | Q(authors__last_name__icontains=value)
        )
        return Library.objects.filter(f).distinct()[:5]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {"libraries": serializer.data},
            template_name="libraries/includes/search_results.html",
        )
