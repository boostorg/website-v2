# from django.db import models
# from django.shortcuts import redirect, render
# from django.contrib import messages
#
# from wagtail.models import Page
# from wagtail.fields import RichTextField
# from wagtail.admin.panels import FieldPanel
#
# from .forms import CapturedEmailForm
#
#
# class HomePage(Page):
#     subpage_types = [
#         "marketing.WhitepapersIndexPage",
#         # ... other allowed children
#     ]
#
#
# class WhitepapersIndexPage(Page):
#     """Index holder at /whitepapers/."""
#     # Only allow category pages underneath
#     subpage_types = ["marketing.WhitepaperCategoryPage"]
#     parent_page_types = ["home.HomePage"]
#
#     # Optional: editor help text, etc.
#     content_panels = Page.content_panels
#
#
# class WhitepaperCategoryPage(Page):
#     """
#     Category container at /whitepapers/<category>/
#     Use this page’s slug as the <category> segment.
#     """
#     # Only allow landing pages underneath
#     subpage_types = ["marketing.WhitepaperLandingPage"]
#     parent_page_types = ["marketing.WhitepapersIndexPage"]
#
#     content_panels = Page.content_panels
#
#
# class WhitepaperLandingPage(Page):
#     """
#     Final landing page at /whitepapers/<category>/<slug>/
#     Replaces your old LandingPage model.
#     """
#     call_to_action = models.TextField(
#         default="Drop your email below to get engineering updates."
#     )
#     privacy_blurb = models.TextField(
#         default="Privacy: no spam, one step unsubscribe. We'll only send high-signal dev content about Boost libraries."
#     )
#     # RichTextField gives editors basic formatting; switch to StreamField if you want components/blocks
#     content = RichTextField(features=["h2", "h3", "bold", "italic", "link", "ol", "ul"])
#
#     # Tree rules
#     parent_page_types = ["marketing.WhitepaperCategoryPage"]
#     subpage_types = []  # leaf
#
#     content_panels = Page.content_panels + [
#         FieldPanel("call_to_action"),
#         FieldPanel("privacy_blurb"),
#         FieldPanel("content"),
#     ]
#
#     template = "marketing/landing_page.html"
#
#     # --- View logic (combined Detail + Create) ---
#     def serve(self, request):
#         # Build the email form
#         if request.method == "POST":
#             form = CapturedEmailForm(request.POST)
#             if form.is_valid():
#                 inst = form.save(commit=False)
#                 original_referrer = request.session.get("original_referrer", "")
#                 inst.referrer = original_referrer or request.META.get("HTTP_REFERER", "")
#                 # parent slug is the category
#                 category = self.get_parent().slug if self.get_parent() else ""
#                 inst.page_slug = f"{category}/{self.slug}".strip("/")
#                 inst.save()
#                 messages.success(request, "Thanks! We'll be in touch.")
#                 return redirect(self.url)  # show success message on same page
#         else:
#             form = CapturedEmailForm()
#
#         return render(
#             request,
#             self.get_template(request),
#             {
#                 "page": self,   # Wagtail convention
#                 "form": form,   # your template expects {{ form }}
#             },
#         )
