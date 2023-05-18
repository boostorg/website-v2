from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404, HttpResponseRedirect
from django.utils.translation import gettext as _
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    View,
)
from django.views.generic.detail import SingleObjectMixin

from .models import Entry
from .forms import EntryForm


def get_published_or_none(sibling_getter):
    """Helper method to get next/prev published sibling of a given entry."""
    try:
        result = sibling_getter(published=True)
    except Entry.DoesNotExist:
        result = None
    return result


class EntryListView(ListView):
    model = Entry
    template_name = "news/list.html"
    ordering = ["-publish_at"]
    paginate_by = 10

    def get_queryset(self):
        return super().get_queryset().filter(published=True)


class EntryDetailView(DetailView):
    model = Entry
    template_name = "news/detail.html"

    def get_object(self, *args, **kwargs):
        # Published news are available to anyone, otherwise to authors only
        result = super().get_object(*args, **kwargs)
        if not result.can_view(self.request.user):
            raise Http404()
        return result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = get_published_or_none(self.object.get_next_by_publish_at)
        context["prev"] = get_published_or_none(self.object.get_previous_by_publish_at)
        context["user_can_approve"] = self.object.can_approve(self.request.user)
        return context


class EntryCreateView(LoginRequiredMixin, CreateView):
    model = Entry
    form_class = EntryForm
    template_name = "news/form.html"

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)


class EntryApproveView(
    LoginRequiredMixin, UserPassesTestMixin, SingleObjectMixin, View
):
    model = Entry
    http_method_names = ["post"]

    def test_func(self):
        entry = self.get_object()
        return entry.can_approve(self.request.user)

    def post(self, request, *args, **kwargs):
        entry = self.get_object()
        try:
            entry.approve(user=self.request.user)
        except Entry.AlreadyApprovedError:
            messages.error(request, _("The entry was already approved."))
        else:
            messages.success(request, _("The entry was successfully approved."))
        return HttpResponseRedirect(entry.get_absolute_url())
