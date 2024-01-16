from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.humanize.templatetags import humanize
from django.contrib.messages.views import SuccessMessageMixin
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect
from django.template.defaultfilters import date as datefilter
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import now
from django.utils.translation import gettext as _
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)
from django.views.generic.detail import SingleObjectMixin

from .acl import can_approve
from .forms import BlogPostForm, EntryForm, LinkForm, NewsForm, PollForm, VideoForm
from .models import BlogPost, Entry, Link, News, Poll, Video
from .notifications import (
    send_email_news_approved,
    send_email_news_needs_moderation,
    send_email_news_posted,
)


def get_published_or_none(sibling_getter):
    """Helper method to get next/prev published sibling of a given entry."""
    try:
        result = sibling_getter(published=True)
    except Entry.DoesNotExist:
        result = None
    return result


def display_publish_at(publish_at, since=None):
    """Show "Time since".

    An hour ago (up to 24 hours)
    3 days ago (up to 7 days)
    June 13th, 2023 (after 7 days)

    """
    if since is None:
        since = now()

    if publish_at > since:
        publish_at = since

    diff = since - publish_at
    if diff.days >= 7:
        return datefilter(publish_at, "M jS, Y")

    if diff.days > 0:
        truncated = since - timedelta(days=diff.days)
    else:
        hours = round(diff.seconds / 3600)
        truncated = since - timedelta(hours=hours)

    return humanize.naturaltime(truncated).replace("\xa0", " ")


class EntryListView(ListView):
    model = Entry
    template_name = "news/list.html"
    ordering = ["-publish_at"]
    paginate_by = None  #  XXX: use pagination in the template! Issue #377
    context_object_name = "entry_list"  # Ensure children use the same name

    def get_queryset(self):
        result = super().get_queryset().select_related("author").filter(published=True)
        right_now = now()
        for entry in result:
            entry.display_publish_at = display_publish_at(entry.publish_at, right_now)
        return result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_moderator"] = False

        if self.request.user.is_authenticated:
            context["is_moderator"] = can_approve(self.request.user)
        return context


class BlogPostListView(EntryListView):
    model = BlogPost


class LinkListView(EntryListView):
    model = Link


class NewsListView(EntryListView):
    model = News


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
        return can_approve(self.request.user)


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


class EntryCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = None
    form_class = None
    template_name = "news/form.html"
    add_label = None
    add_url_name = None
    success_message = _("The news entry was successfully created.")

    def form_valid(self, form):
        form.instance.author = self.request.user
        result = super().form_valid(form)
        if not form.instance.is_approved:
            send_email_news_needs_moderation(request=self.request, entry=form.instance)
        else:
            send_email_news_posted(request=self.request, entry=form.instance)
        return result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["add_label"] = self.add_label
        context["add_url_name"] = self.add_url_name
        context["cancel_url"] = reverse_lazy("news")
        return context


class BlogPostCreateView(EntryCreateView):
    model = BlogPost
    form_class = BlogPostForm
    add_label = _("Create Blog Post")
    add_url_name = "news-blogpost-create"


class LinkCreateView(EntryCreateView):
    model = Link
    form_class = LinkForm
    add_label = _("Create Link")
    add_url_name = "news-link-create"


class NewsCreateView(EntryCreateView):
    model = News
    form_class = NewsForm
    add_label = _("Create News")
    add_url_name = "news-news-create"


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


class AllTypesCreateView(LoginRequiredMixin, TemplateView):
    template_name = "news/create.html"
    http_method_names = ["get"]  # This is a "create news" multiplexer (by news type)

    @staticmethod
    def item_params(view):
        return {
            "form": view.form_class(),
            "model_name": view.model.__name__,
            "add_label": view.add_label,
            "add_url_name": view.add_url_name,
        }

    def dispatch(self, request, *args, **kwargs):
        """User must have a profile photo and a name to post an entry."""
        if request.user.is_authenticated:
            missing_data = []

            if not request.user.first_name and not request.user.last_name:
                missing_data.append("your name")

            if not request.user.image:
                missing_data.append("a profile photo")

            if missing_data:
                messages.warning(
                    request, f"Please add {' and '.join(missing_data)} first."
                )
                return redirect("profile-account")

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        items = [
            self.item_params(BlogPostCreateView),
            self.item_params(LinkCreateView),
            self.item_params(NewsCreateView),
            self.item_params(VideoCreateView),
        ]
        # Only superusers and moderators can create Polls
        if can_approve(self.request.user):
            items.append(self.item_params(PollCreateView))
        context["items"] = items
        return context


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
            send_email_news_approved(request=request, entry=entry)
            send_email_news_posted(request=request, entry=entry)

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
        elif self.object.is_news:
            result = NewsForm
        elif self.object.is_poll:
            result = PollForm
        elif self.object.is_video:
            result = VideoForm
        else:
            result = EntryForm
        return result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = reverse_lazy(
            "news-detail", kwargs={"slug": self.object.slug}
        )
        return context


class EntryDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Entry
    template_name = "news/confirm_delete.html"
    success_url = reverse_lazy("news")

    def test_func(self):
        entry = self.get_object()
        return entry.can_delete(self.request.user)
