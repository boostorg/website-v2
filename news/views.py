from django.views.generic import DetailView, ListView
from django.utils.timezone import now

from .models import Entry


def get_published_or_none(sibling_getter):
    """Helper method to get next/prev published sibling of a given entry."""
    try:
        result = sibling_getter(publish_at__lte=now())
    except Entry.DoesNotExist:
        result = None
    return result


class EntryListView(ListView):
    model = Entry
    template_name = "news/list.html"
    ordering = ["-publish_at"]
    paginate_by = 10

    def get_queryset(self):
        return super().get_queryset().filter(publish_at__lte=now())


class EntryDetailView(DetailView):
    model = Entry
    template_name = "news/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = get_published_or_none(self.object.get_next_by_publish_at)
        context["prev"] = get_published_or_none(self.object.get_previous_by_publish_at)
        return context
