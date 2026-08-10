from datetime import timedelta
from functools import partial

import requests
import structlog

from django.conf import settings
from django.forms import ValidationError
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.humanize.templatetags import humanize
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.http import (
    Http404,
    HttpResponseRedirect,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import redirect, get_object_or_404
from django.template.defaultfilters import date as datefilter
from django.urls import reverse, reverse_lazy
from django.utils.functional import cached_property
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import localtime, now
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
from django.views.decorators.http import require_POST
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadData
from wagtail.blocks import Block
from wagtail.images.models import Image
from wagtail.models import Page

from core.mixins import V3Mixin
from pages.blocks import NEWS_BLOCK, BLOG_BLOCK, LINK_BLOCK, VIDEO_BLOCK
from pages.models import PostPage, PostIndexPage
from pages.mixins import ContentTag
from users.profile_cards import user_profile_card
from .acl import can_approve
from .constants import (
    NEWS_APPROVAL_SALT,
    MAGIC_LINK_EXPIRATION,
    DESCRIPTION_SUMMARY_MAX_LENGTH,
)

from .forms import (
    BlogPostForm,
    EntryForm,
    LinkForm,
    NewsForm,
    PollForm,
    VideoForm,
    V3BlogPostForm,
    V3LinkForm,
    V3NewsForm,
    V3VideoForm,
)
from .models import BlogPost, Entry, Link, News, Poll, Video
from .services import news_type_label
from .tasks import generate_summary
from .helpers import UnsafeURLError, extract_article, extract_content, safe_get
from .notifications import (
    send_email_news_approved,
    send_email_news_needs_moderation,
    send_email_news_posted,
)
from news.utils import downsize_uploaded_image

from libraries.models import Library

User = get_user_model()
logger = structlog.get_logger(__name__)


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


class EntryListView(V3Mixin, ListView):
    model = Entry
    template_name = "news/list.html"
    v3_template_name = "v3/posts_list.html"
    ordering = ["-publish_at"]
    paginate_by = 10
    context_object_name = "entry_list"  # Ensure children use the same name
    header_text = "Latest Posts"
    filter_value = "all"

    @cached_property
    def libary_values(self):
        return [(x.slug, x.name) for x in Library.objects.all().order_by("name")]

    def get_v3_context_data(self, **kwargs):
        return {
            "filter_terms": [
                {"label": "All", "value": "all", "url": reverse("news")},
                {"label": "News", "value": "news", "url": reverse("news-news-list")},
                {
                    "label": "Blogs",
                    "value": "blogpost",
                    "url": reverse("news-blogpost-list"),
                },
                {"label": "Links", "value": "link", "url": reverse("news-link-list")},
                {
                    "label": "Videos",
                    "value": "video",
                    "url": reverse("news-video-list"),
                },
                {
                    "label": "Discussions",
                    "value": "discussions",
                    "url": reverse("news"),
                },
                {
                    "label": "Achievements",
                    "value": "achievements",
                    "url": reverse("news"),
                },
                {"label": "Issues", "value": "issues", "url": reverse("news")},
            ],
            "libraries": self.libary_values,
            "header_text": self.header_text,
            "filter_value": self.filter_value,
            **kwargs,
        }

    def get_queryset(self):
        if self.request.GET.get("sort") == "popular":
            result = (
                self.model.objects.ranked()
                .select_related("author")
                .filter(published=True, deleted_at__isnull=True)
            )
        else:
            result = (
                super()
                .get_queryset()
                .select_related("author")
                .filter(published=True, deleted_at__isnull=True)
            )
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

    def dispatch(self, request, *args, **kwargs):
        if post_filter := self.request.GET.get("post-filter"):
            match post_filter:
                case "all":
                    return HttpResponseRedirect(reverse_lazy("news"))
                case "blogpost":
                    return HttpResponseRedirect(reverse_lazy("news-blogpost-list"))
                case "video":
                    return HttpResponseRedirect(reverse_lazy("news-video-list"))
                case "news":
                    return HttpResponseRedirect(reverse_lazy("news-news-list"))
                case "link":
                    return HttpResponseRedirect(reverse_lazy("news-link-list"))
        return super().dispatch(request, *args, **kwargs)


class BlogPostListView(EntryListView):
    header_text = "Blogs"
    model = BlogPost
    filter_value = "blogpost"


class LinkListView(EntryListView):
    header_text = "Links"
    model = Link
    filter_value = "link"


class NewsListView(EntryListView):
    header_text = "News"
    model = News
    filter_value = "news"


class PollListView(EntryListView):
    header_text = "Polls"
    model = Poll


class VideoListView(EntryListView):
    header_text = "Videos"
    model = Video
    filter_value = "video"


class EntryModerationListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Entry
    template_name = "news/moderation.html"
    ordering = ["-publish_at"]
    paginate_by = None

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("author")
            .filter(approved=False, deleted_at__isnull=True)
        )

    def test_func(self):
        return can_approve(self.request.user)


class EntryDetailView(V3Mixin, DetailView):
    model = Entry
    template_name = "news/detail.html"
    v3_template_name = "news/v3/detail.html"

    AUTHOR_PREFETCH = ("author__maintainers",)

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "_v3_active", False):
            qs = qs.select_related("author").prefetch_related(*self.AUTHOR_PREFETCH)
        return qs

    def get_object(self, *args, **kwargs):
        # Published news are available to anyone,
        # otherwise to authors and moderators only
        result = super().get_object(*args, **kwargs)
        if not result.can_view(self.request.user):
            raise Http404()
        return result

    def get_v3_context_data(self, **kwargs):
        context = super().get_v3_context_data(**kwargs)
        self.object = self.get_object()
        entry = self.object
        next_entry = (
            Entry.objects.published()
            .select_related("author")
            .prefetch_related(*self.AUTHOR_PREFETCH)
            .filter(publish_at__gt=entry.publish_at, deleted_at__isnull=True)
            .exclude(pk=entry.pk)
            .order_by("publish_at", "pk")
            .first()
        )
        # TODO: once Entry has a relation to libraries, scope related
        # posts to those linked to the libraries referenced by this
        # entry. Falls back to "any other published post" until that
        # relation exists.
        related_qs = (
            Entry.objects.published()
            .select_related("author")
            .prefetch_related(*self.AUTHOR_PREFETCH)
            .filter(deleted_at__isnull=True)
            .exclude(pk=entry.pk)
        )
        if next_entry is not None:
            related_qs = related_qs.exclude(pk=next_entry.pk)
        v3_context = {
            "post_author": user_profile_card(entry.author),
            "post_tag": news_type_label(entry.tag),
            "next_post_items": (
                [self._post_card_item(next_entry)] if next_entry else []
            ),
            "related_posts": [
                self._post_card_item(e)
                for e in related_qs.order_by("-publish_at", "-pk")[:3]
            ],
        }
        context.update(v3_context)
        return context

    @classmethod
    def _post_card_item(cls, entry):
        return {
            "title": entry.title,
            "description": entry.summary or "",
            "url": reverse("news-detail", args=[entry.slug]),
            "date": entry.publish_at,
            "category": news_type_label(entry.tag),
            "author": user_profile_card(entry.author),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        next_url = self.request.GET.get("next")
        if url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
            context["next_url"] = next_url
        context["user_can_approve"] = self.object.can_approve(self.request.user)
        context["user_can_edit"] = self.object.can_edit(self.request.user)
        context["user_can_delete"] = self.object.can_delete(self.request.user)
        if getattr(self, "_v3_active", False):
            return context
        context["next"] = get_published_or_none(self.object.get_next_by_publish_at)
        context["prev"] = get_published_or_none(self.object.get_previous_by_publish_at)
        if self.object.tag:
            category_kwarg = {f"{self.object.tag}__isnull": False}
        else:
            category_kwarg = {}
        context["next_in_category"] = get_published_or_none(
            partial(self.object.get_next_by_publish_at, **category_kwarg)
        )
        context["prev_in_category"] = get_published_or_none(
            partial(self.object.get_previous_by_publish_at, **category_kwarg)
        )
        return context


class EntryModerationDetailView(LoginRequiredMixin, EntryDetailView):
    v3_template_name = None


class EntryModerationMagicApproveView(View):
    """Approve a news entry without requiring moderator login."""

    def get(self, request, token, *args, **kwargs):
        serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
        try:
            data = serializer.loads(
                token, salt=NEWS_APPROVAL_SALT, max_age=MAGIC_LINK_EXPIRATION
            )
            entry_slug = data["entry_slug"]
            moderator_id = data["moderator_id"]
            moderator = User.objects.get(id=moderator_id)
        except SignatureExpired:
            message = _("This link has expired.")
            if not request.user.is_authenticated:
                message += _(" Please login to continue.")
            messages.warning(request, message)
            return redirect(reverse_lazy("news-moderate"))
        except (BadData, User.DoesNotExist):
            return HttpResponseForbidden("Invalid magic link.")

        entry = get_object_or_404(Entry, slug=entry_slug)

        try:
            entry.approve(moderator)
            messages.success(request, _("This entry has been approved."))
        except Entry.AlreadyApprovedError:
            messages.warning(request, _("This entry has already been approved."))

        return redirect(entry)


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
    post_type_selected = "blog"


class LinkCreateView(EntryCreateView):
    model = Link
    form_class = LinkForm
    add_label = _("Create Link")
    add_url_name = "news-link-create"
    post_type_selected = "link"


class NewsCreateView(EntryCreateView):
    model = News
    form_class = NewsForm
    add_label = _("Create News")
    add_url_name = "news-news-create"
    post_type_selected = "news"


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
    post_type_selected = "video"


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

            if not request.user.display_name:
                missing_data.append("your name")

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


class V3AllTypesCreateView(V3Mixin, AllTypesCreateView):
    v3_template_name = "news/v3/create.html"
    http_method_names = ["get", "post"]

    _POST_BLOCK_MAP: dict[str, tuple[str, Block]] = {
        "blog": BLOG_BLOCK,
        "news": NEWS_BLOCK,
        "link": LINK_BLOCK,
        "video": VIDEO_BLOCK,
    }

    _POST_TYPE_MAP = {
        "blog": V3BlogPostForm,
        "news": V3NewsForm,
        "link": V3LinkForm,
        "video": V3VideoForm,
    }

    def dispatch(self, request, *args, **kwargs):
        # Run AllTypesCreateView's profile-completeness guard before V3Mixin takes over.
        response = AllTypesCreateView.dispatch(self, request, *args, **kwargs)
        if response.status_code != 200:
            return response
        return super().dispatch(request, *args, **kwargs)

    def _v3_create_context(self):
        """Shared context variables needed by the v3 create-post template."""
        return {
            "post_type_options": [
                ("blog", "Blog"),
                ("news", "News"),
                ("video", "Video"),
                ("link", "Link"),
            ],
            "related_libraries_options": [
                (
                    library.slug,
                    library.name,
                )
                for library in Library.objects.all().order_by("name")
            ],
            "publish_at_initial": localtime(now()).strftime("%Y-%m-%dT%H:%M"),
            "title": "Create Post",
            "edit": False,
        }

    def get_v3_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._v3_create_context())
        return context

    def error_message_and_render(self, message: str, extra_context: dict | None = None):
        messages.error(self.request, message)
        if extra_context:
            context = self.get_context_data(**extra_context)
        return self.render_to_response(context)

    def set_page_attrs(
        self,
        page: PostPage,
        form,
        related_libraries: list,
        block_name: str,
        post_type: str,
    ):
        cleaned_data = form.cleaned_data
        page.title = cleaned_data.get("title")
        page.summary = cleaned_data.get("summary", "")
        page.go_live_at = cleaned_data.get("publish_at")
        page.content = [
            (
                block_name,
                cleaned_data.get("content") or cleaned_data.get("external_url"),
            )
        ]
        page.live = False
        if image := cleaned_data.get("image"):
            if image.size >= settings.DOWNSCALE_IMAGE_THRESHOLD:
                image = downsize_uploaded_image(image)
            wagtail_image = Image.objects.create(
                title=image.name,
                file=image,
            )
            page.image = wagtail_image
        tags = []
        if related_libraries:
            for library in related_libraries:
                lib = Library.objects.get(slug=library)
                tag, created = ContentTag.objects.get_or_create(
                    slug=lib.slug,
                    defaults={
                        "name": lib.name,
                    },
                )
                tags.append(tag)
        if tags:
            page.tags.set(tags)

        return page

    def post(self, request, *args, **kwargs):
        post_type = request.POST.get("post_type", "")
        block_config = self._POST_BLOCK_MAP.get(post_type, None)
        form_class = self._POST_TYPE_MAP.get(post_type)

        if block_config is None or form_class is None:
            return self.error_message_and_render(
                message=_(
                    "Invalid post type selected. Please choose a valid post type."
                )
            )
        block_name, block_class = block_config

        # The v3 create page has two Description textareas — `description` for
        # Blog/News and `link_description` for Link/Video — so the two don't
        # collide in the submitted form. Bind whichever applies to the model's
        # `summary` field on submit for the forms that include it.
        post_data = request.POST.copy()
        description_field = (
            "link_description" if post_type in ("link", "video") else "description"
        )
        if post_data.get(description_field) and not post_data.get("summary"):
            post_data["summary"] = post_data[description_field]
        form = form_class(post_data, request.FILES)

        if form.is_valid():
            # Since the PostIndexPage is limited to one, we can just grab the first
            index_page = PostIndexPage.objects.first()
            if not index_page:
                return self.error_message_and_render(
                    _(
                        "An internal database error has occurred. Please contact an admin."
                    ),
                    {"form": form, "post_type_selected": post_type},
                )

            try:
                page = PostPage()
                page.owner = request.user
                try:
                    page = self.set_page_attrs(
                        page=page,
                        form=form,
                        block_name=block_name,
                        post_type=post_type,
                        related_libraries=post_data.getlist("related_libraries"),
                    )
                except Library.DoesNotExist:
                    return self.error_message_and_render(
                        _(
                            "That related library does not exist, please select another."
                        ),
                        {"form": form, "post_type_selected": post_type},
                    )
                index_page.add_child(instance=page)
                page.save_revision(user=request.user)
                page.get_workflow().start(obj=page, user=request.user)
            except ValidationError as e:
                if "slug" in str(e):
                    form.add_error(
                        "title",
                        "A post with this title already exists. Please choose a different title.",
                    )
                else:
                    form.add_error(
                        None, "An unexpected error occurred. Please try again."
                    )
                    messages.error(
                        request,
                        _(
                            "Something went wrong — your draft is saved, so give it another try."
                        ),
                    )
                context = self.get_context_data(form=form, post_type_selected=post_type)
                return self.render_to_response(context)

            messages.success(
                request,
                _(
                    "Your post has been submitted. It'll be reviewed before it goes live, you will receive updates via email."
                ),
            )
            return redirect(index_page.url)

        context = self.get_context_data(form=form, post_type_selected=post_type)
        return self.render_to_response(context)


class V3AllTypesEditView(V3AllTypesCreateView):
    _page = PostPage.objects.none()

    def _v3_edit_context(self, page: PostPage):
        ctx = {}
        ctx["edit"] = True
        ctx["title"] = "Edit Post"
        ctx["publish_at_initial"] = localtime(now()).strftime("%Y-%m-%dT%H:%M")
        ctx["related_libraries_options"] = [
            (
                library.slug,
                library.name,
            )
            for library in Library.objects.all().order_by("name")
        ]

        if not page:
            return ctx
        ctx["post_type_selected"] = page.stream_content_type
        ctx["post_type_options"] = [
            (page.stream_content_type, page.post_content_type),
        ]

        if page.image:
            ctx["current_image"] = page.image_url

        form_class = self._POST_TYPE_MAP.get(page.stream_content_type, None)
        if not form_class:
            messages.error(
                self.request,
                _("An internal database error has occurred. Please contact an admin."),
            )
            return ctx

        form_data = {
            "title": page.title,
            "summary": page.summary,
            "related_libraries": list(page.tags.all().values_list("slug", flat=True)),
        }
        go_live = page.go_live_at or localtime(now())
        form_data["publish_at"] = go_live.strftime("%Y-%m-%dT%H:%M")
        if page.stream_content_type in ["video", "link"]:
            form_data["external_url"] = page.external_url
        else:
            form_data["content"] = page.content

        form = form_class(initial=form_data)
        ctx["form"] = form

        return ctx

    def get_v3_context_data(self, **kwargs):
        page = self._page
        context = super().get_v3_context_data(**kwargs)
        context["related_libraries"] = list(
            page.tags.all().values_list("slug", flat=True)
        )
        context.update(self._v3_edit_context(page))
        return context

    def get_page(self, slug):
        index_page = PostIndexPage.objects.first()
        if not index_page:
            messages.error(
                self.request,
                _("An internal database error has occurred. Please contact an admin."),
            )
            return
        try:
            page: PostPage = (
                PostPage.objects.child_of(index_page)
                .get(slug=slug)
                .get_latest_revision_as_object()
            )
        except PostPage.DoesNotExist:
            messages.error(
                self.request,
                _("No page with slug %(slug)s exists…") % {"slug": slug},
            )
            return

        if not self.request.user == page.owner:
            raise PermissionDenied("Only the author of a page may edit it.")

        self._page = page

    def get(self, request, *args, **kwargs):
        slug = kwargs.get("slug", "")
        self.get_page(slug)

        if self._page and not self._page.user_can_edit(request.user):
            raise PermissionDenied("You do not have permission to edit this page.")

        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        slug = kwargs.get("slug", "")
        index_page = PostIndexPage.objects.first()
        if not index_page:
            return self.error_message_and_render(
                _("An internal database error has occurred. Please contact an admin."),
            )
        try:
            page: PostPage = index_page.get_children().get(slug=slug).specific
        except Page.DoesNotExist:
            messages.error(
                self.request,
                _("No page with slug %(slug)s exists…") % {"slug": slug},
            )
            context = self.get_context_data()
            return self.render_to_response(context)

        post_type = page.stream_content_type
        block_config = self._POST_BLOCK_MAP.get(post_type, None)
        form_class = self._POST_TYPE_MAP.get(post_type)

        if block_config is None or form_class is None:
            return self.error_message_and_render(
                message=_(
                    "Invalid post type selected. Please choose a valid post type."
                )
            )

        block_name, block_class = block_config

        # The v3 create page has two Description textareas — `description` for
        # Blog/News and `link_description` for Link/Video — so the two don't
        # collide in the submitted form. Bind whichever applies to the model's
        # `summary` field on submit for the forms that include it.
        post_data = request.POST.copy()
        description_field = (
            "link_description" if post_type in ("link", "video") else "description"
        )
        if post_data.get(description_field) and not post_data.get("summary"):
            post_data["summary"] = post_data[description_field]

        form = form_class(post_data, request.FILES)
        if form.is_valid():
            if not page.user_can_edit(request.user):
                messages.error(
                    self.request,
                    _("You do not have permission to edit this page."),
                )
                context = self.get_context_data(form=form, post_type_selected=post_type)
                return self.render_to_response(context)

            try:
                page = self.set_page_attrs(
                    page=page,
                    form=form,
                    block_name=block_name,
                    post_type=post_type,
                    related_libraries=post_data.getlist("related_libraries"),
                )
                page.save_revision(user=request.user)
                if not page.workflow_in_progress:
                    page.get_workflow().start(obj=page, user=request.user)
            except Library.DoesNotExist:
                return self.error_message_and_render(
                    _("That related library does not exist, please select another."),
                    {"form": form, "post_type_selected": post_type, "slug": slug},
                )
            except ValidationError as e:
                if "slug" in str(e):
                    form.add_error(
                        "title",
                        "A post with this title already exists. Please choose a different title.",
                    )
                else:
                    form.add_error(
                        None, "An unexpected error occurred. Please try again."
                    )
                    messages.error(
                        request,
                        _(
                            "Something went wrong — your draft is saved, so give it another try."
                        ),
                    )
                context = self.get_context_data(
                    form=form,
                    post_type_selected=post_type,
                    related_libraries=post_data.getlist("related_libraries"),
                )
                return self.render_to_response(context)

            messages.success(
                request,
                _(
                    "Your post has been submitted. It'll be reviewed before it goes live, you will receive updates via email."
                ),
            )
            return redirect(index_page.url)

        context = self.get_context_data(form=form, post_type_selected=post_type)
        return self.render_to_response(context)


class V3DeletePostView(V3Mixin, LoginRequiredMixin, View):
    def post(self, request, **kwargs):
        slug = kwargs.get("slug")
        if not slug:
            messages.error(request, message=_("No slug was provided to delete"))
            return redirect(reverse("news"))
        index_page = PostIndexPage.objects.first()
        if not index_page:
            messages.error(
                request=request,
                message=_(
                    "An internal database error has occurred. Please contact an admin."
                ),
            )
            return redirect(reverse("news"))
        try:
            page: PostPage = index_page.get_children().get(slug=slug).specific
        except Page.DoesNotExist:
            messages.error(
                request,
                _("No page with slug %(slug)s exists…") % {"slug": slug},
            )
            return redirect(reverse("news"))

        if not page.user_can_delete(request.user):
            messages.error(request=request, message=_("You do not own this page."))
            return redirect(page.url)

        page.unpublish(user=request.user)
        messages.success(
            request=request, message=_("This page has been successfully removed.")
        )
        return redirect(reverse("news"))


@login_required
@require_POST
def generate_description(request):
    """Generate an AI description from submitted content (synchronous).

    Backs the "Auto-Generate Description" button on the v3 create-post page.
    Runs the summarization model inline and returns the result as JSON so the
    browser can drop it into the Description field.

    Login-gated since it calls a paid LLM. NOTE: still no rate limiting — add
    per-user throttling before relying on auth alone to bound spend.
    """
    title = request.POST.get("title", "").strip()
    content = request.POST.get("content", "").strip()

    if not content:
        return JsonResponse({"error": "Add some content first."}, status=400)

    # The Blog/News body comes from the WYSIWYG editor as rich-text HTML. Strip
    # it to plain text before summarizing: the markup inflates the payload (a
    # cold model call on the full HTML can exceed the gateway timeout and 504)
    # and only muddies the summary. No-op on content that's already plain text.
    content = extract_content(content)

    try:
        # Call the plain helper
        summary = generate_summary(
            content,
            title,
            settings.SUMMARIZATION_MODEL,
            DESCRIPTION_SUMMARY_MAX_LENGTH,
            timeout=30,
        )
    except Exception:
        logger.exception("generate_description: summarization failed")
        return JsonResponse(
            {"error": "Could not generate a description. Please try again."},
            status=502,
        )

    if not summary:
        return JsonResponse(
            {"error": "Could not generate a description. Please try again."},
            status=502,
        )

    return JsonResponse({"description": summary.strip()})


_LINK_FETCH_ERROR = "We couldn't read that link. Please check the URL and try again."
_LINK_INVALID_ERROR = "Please enter a valid, public http(s) link."


@login_required
@require_POST
def generate_link_description(request):
    """Fetch the linked page, extract its main text, and summarize it.

    Works for any public http(s) URL (trafilatura isolates the main article and
    falls back to a visible-text dump for unusual templates). The fetch goes
    through ``safe_get``, which blocks SSRF to internal/private hosts and
    re-validates redirect targets.

    Failure modes return separate JSON errors:
      - URL is missing, malformed, or points at a non-public host (400).
      - Fetch failed or no readable text could be extracted (502, "couldn't
        read that link").
      - Summarization failed or returned empty (502, "couldn't generate").

    NOTE: still no rate limiting — add per-user throttling before relying on
    auth alone to bound spend.
    """
    url = request.POST.get("url", "").strip()
    if not url:
        return JsonResponse({"error": _LINK_INVALID_ERROR}, status=400)

    try:
        resp = safe_get(url, timeout=10)
        resp.raise_for_status()
    except UnsafeURLError:
        logger.warning("generate_link_description: blocked unsafe url", url=url)
        return JsonResponse({"error": _LINK_INVALID_ERROR}, status=400)
    except requests.RequestException:
        logger.exception("generate_link_description: fetch failed", url=url)
        return JsonResponse({"error": _LINK_FETCH_ERROR}, status=502)

    title, body = extract_article(resp.text, url=url)
    if not body:
        # Page fetched OK but no readable text could be isolated.
        logger.warning("generate_link_description: extraction empty", url=url)
        return JsonResponse({"error": _LINK_FETCH_ERROR}, status=502)

    # Feed the extracted body through the same summarizer used by the Blog/News
    # path — synchronously, with a real timeout so a hung upstream doesn't tie
    # up a web worker (autoretry_for on the Celery task is a no-op when called
    # inline; see news/tasks.py).
    try:
        summary = generate_summary(
            body,
            title,
            settings.SUMMARIZATION_MODEL,
            DESCRIPTION_SUMMARY_MAX_LENGTH,
            timeout=30,
        )
    except Exception:
        logger.exception("generate_link_description: summarization failed", url=url)
        return JsonResponse(
            {"error": "Could not generate a description. Please try again."},
            status=502,
        )

    if not summary:
        return JsonResponse(
            {"error": "Could not generate a description. Please try again."},
            status=502,
        )

    return JsonResponse({"description": summary.strip()})


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

    def form_valid(self, form):
        self.object.deleted_at = now()
        self.object.deleted_by = self.request.user
        self.object.save(update_fields=["deleted_at", "deleted_by"])
        return HttpResponseRedirect(self.get_success_url())

    def test_func(self):
        entry = self.get_object()
        return entry.can_delete(self.request.user)
