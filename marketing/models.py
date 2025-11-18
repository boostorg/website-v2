from django import forms
from django.contrib import messages
from django.db import models
from django.http import Http404
from django.shortcuts import render, redirect
from wagtail.admin.panels import FieldPanel
from wagtail.blocks import RichTextBlock
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.url_routing import RouteResult
from wagtailmarkdown.blocks import MarkdownBlock

RICH_TEXT_FEATURES = [
    "h1",
    "h2",
    "h3",
    "bold",
    "italic",
    "link",
    "ol",
    "ul",
    "code",
    "blockquote",
]


class CapturedEmail(models.Model):
    email = models.EmailField()
    referrer = models.CharField(blank=True, default="")
    page = models.ForeignKey(
        Page,
        related_name="captured_emails",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.pk}): {self}>"


class CapturedEmailForm(forms.ModelForm):
    class Meta:
        model = CapturedEmail
        fields = ["email"]
        widgets = {
            "email": forms.EmailInput(
                attrs={"placeholder": "your@email.com", "autocomplete": "email"}
            )
        }


class EmailCapturePage(Page):
    """Abstract page with reusable logic for pages that capture an email."""

    email_capture_intro = models.TextField(
        default="Drop your email below to get engineering updates."
    )
    privacy_blurb = models.TextField(
        default="Privacy: no spam, one step unsubscribe. We'll only send high-signal dev content re this and other Boost libraries."
    )
    body = StreamField(
        [
            ("rich", RichTextBlock(features=RICH_TEXT_FEATURES, label="Rich text")),
            ("md", MarkdownBlock(label="Markdown")),
        ],
        use_json_field=True,
        blank=True,
    )
    content_panels = Page.content_panels + [
        FieldPanel("email_capture_intro"),
        FieldPanel("privacy_blurb"),
        FieldPanel("body"),
    ]

    class Meta:
        abstract = True

    def get_referrer(self, request):
        original = request.session.get("original_referrer", "")
        return original or request.headers.get("referer", "")

    def build_form(self, request) -> CapturedEmailForm:
        """Create a form instance appropriate to the request method."""
        if request.method == "POST":
            return CapturedEmailForm(data=request.POST)
        return CapturedEmailForm()

    def get_success_url(self, request):
        """Redirect back to the same page after a successful POST."""
        return self.url

    def handle_email_form(self, request, form):
        captured = form.save(commit=False)
        captured.referrer = self.get_referrer(request)
        captured.page = self
        captured.save()

        messages.success(request, "Thanks! We'll be in touch.")

        return redirect(self.get_success_url(request))

    def serve(self, request, *args, **kwargs):
        """
        Unified GET/POST handling:
        - On GET: render template with empty form.
        - On POST: validate, save CapturedEmail, redirect, or redisplay with errors.
        """
        form = self.build_form(request)

        if request.method == "POST" and form.is_valid():
            return self.handle_email_form(request, form)

        # Fall through: GET, or invalid POST
        context = super().get_context(request, *args, **kwargs)
        context["form"] = form
        return render(request, self.get_template(request), context)


class ProgramPage(EmailCapturePage):
    parent_page_types = ["marketing.ProgramPageIndex"]
    subpage_types = []


class DetailPage(EmailCapturePage):
    parent_page_types = ["marketing.TopicPage"]
    subpage_types = []


# ===================
###  Dummy pages  ###
# ===================
class OutreachHomePage(Page):
    """A dummy homepage to just return a 404 at the `/outreach/` url"""

    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["marketing.ProgramPageIndex", "marketing.TopicPage"]
    max_count = 1  # one container

    def route(self, request, path_components):
        """
        Custom router so public URLs don't include container slugs.
        /outreach/program_page/<slug>/ => delegate to ProgramPageIndex -> ProgramPage
        /outreach/<topic>/<detail>/ => delegate to TopicPage -> DetailPage
        """
        if not path_components:
            return RouteResult(self)

        first, *rest = path_components

        # Fixed segment for program pages
        if first == "program_page":
            try:
                program_page_index = ProgramPageIndex.objects.child_of(self).get()
            except ProgramPageIndex.DoesNotExist:
                raise Http404("Program index not found")
            # Delegate the remaining segments
            return program_page_index.route(request, rest)

        # Otherwise, first segment should be a TopicPage slug
        try:
            topic = TopicPage.objects.child_of(self).get(slug=first)
        except TopicPage.DoesNotExist:
            raise Http404("Topic not found")

        return topic.route(request, rest)

    # Hide this page publicly: /outreach/ -> 404
    def serve(self, request, *args, **kwargs):
        raise Http404

    def get_sitemap_urls(self, request=None):
        return []


class ProgramPageIndex(Page):
    """A dummy index page to facilitate our url scheme"""

    parent_page_types = ["marketing.OutreachHomePage"]
    subpage_types = ["marketing.ProgramPage"]
    max_count = 1  # one container

    # Hide index page: /outreach/program_page/ -> 404
    def serve(self, request, *args, **kwargs):
        raise Http404

    def get_sitemap_urls(self, request=None):
        return []


class TopicPage(Page):
    """A dummy topic page that represents a given topic (e.g. a library)"""

    parent_page_types = ["marketing.OutreachHomePage"]
    subpage_types = ["marketing.DetailPage"]

    class Meta:
        verbose_name = "Topic"

    # Hide this page publicly: /outreach/ -> 404
    def serve(self, request, *args, **kwargs):
        raise Http404

    def get_sitemap_urls(self, request=None):
        return []
