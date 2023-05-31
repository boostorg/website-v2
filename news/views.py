from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Case, Value, When
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
    View,
)
from django.views.generic.detail import SingleObjectMixin

from .models import BlogPost, Entry, Link, Poll, Video
from .forms import BlogPostForm, EntryForm, LinkForm, PollForm, VideoForm


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
    paginate_by = 100  #  XXX: use pagination in the template! Issue #377
    context_object_name = "entry_list"  # Ensure children use the same name

    def get_queryset(self):
        result = super().get_queryset().filter(published=True)
        if self.model == Entry:
            result = result.select_related("blogpost", "link", "poll", "video")
            result = result.annotate(
                tag=Case(
                    When(blogpost__entry_ptr__isnull=False, then=Value("blogpost")),
                    When(link__entry_ptr__isnull=False, then=Value("link")),
                    When(poll__entry_ptr__isnull=False, then=Value("poll")),
                    When(video__entry_ptr__isnull=False, then=Value("video")),
                    default=Value(""),
                )
            )
        else:
            result = result  # .select_related("entry_ptr")
        return result


class BlogPostListView(EntryListView):
    model = BlogPost


class LinkListView(EntryListView):
    model = Link


class PollListView(EntryListView):
    model = Poll


class VideoListView(EntryListView):
    model = Video


class EntryModerationListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Entry
    template_name = "news/moderation.html"
    ordering = ["-publish_at"]
    paginate_by = None

    def get_queryset(self):
        return super().get_queryset().select_related("author").filter(approved=False)

    def test_func(self):
        return Entry.can_approve(self.request.user)


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
        next_url = self.request.GET.get("next")
        if url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
            context["next_url"] = next_url
        context["next"] = get_published_or_none(self.object.get_next_by_publish_at)
        context["prev"] = get_published_or_none(self.object.get_previous_by_publish_at)
        context["user_can_approve"] = self.object.can_approve(self.request.user)
        context["user_can_edit"] = self.object.can_edit(self.request.user)
        context["user_can_delete"] = self.object.can_delete(self.request.user)
        return context


class EntryCreateView(LoginRequiredMixin, CreateView):
    model = Entry
    form_class = EntryForm
    template_name = "news/form.html"
    add_label = _("Create News")
    add_url_name = "news-create"

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["add_label"] = self.add_label
        context["add_url_name"] = self.add_url_name
        return context


class BlogPostCreateView(EntryCreateView):
    model = BlogPost
    form_class = BlogPostForm
    add_label = _("Create a BlogPost")
    add_url_name = "news-blogpost-create"


class LinkCreateView(EntryCreateView):
    model = Link
    form_class = LinkForm
    add_label = _("Create a Link")
    add_url_name = "news-link-create"


class PollCreateView(EntryCreateView):
    model = Poll
    form_class = PollForm
    add_label = _("Create a Poll")
    add_url_name = "news-poll-create"


class VideoCreateView(EntryCreateView):
    model = Video
    form_class = VideoForm
    add_label = _("Upload a Video")
    add_url_name = "news-video-create"


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

        next_url = request.POST.get("next")
        if next_url is None or not url_has_allowed_host_and_scheme(
            next_url, allowed_hosts=None
        ):
            next_url = entry.get_absolute_url()
        return HttpResponseRedirect(next_url)


class EntryUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Entry
    template_name = "news/form.html"

    def test_func(self):
        entry = self.get_object()
        return entry.can_edit(self.request.user)

    def get_form_class(self):
        if self.object.is_blogpost:
            result = BlogPostForm
        elif self.object.is_link:
            result = LinkForm
        elif self.object.is_poll:
            result = PollForm
        elif self.object.is_video:
            result = VideoForm
        else:
            result = EntryForm
        return result


class EntryDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Entry
    template_name = "news/confirm_delete.html"
    success_url = reverse_lazy("news")

    def test_func(self):
        entry = self.get_object()
        return entry.can_delete(self.request.user)
