from django.views.generic import DetailView, ListView

from .models import Testimonial


class TestimonialsIndexView(ListView):
    """Optional non-Wagtail view for listing testimonials."""

    model = Testimonial
    template_name = "testimonials/testimonials_index_page.html"
    context_object_name = "testimonials"

    def get_queryset(self):
        return Testimonial.objects.live().order_by("-first_published_at")


class TestimonialDetailView(DetailView):
    """Optional non-Wagtail view for testimonial detail."""

    model = Testimonial
    template_name = "testimonials/testimonial.html"
    slug_field = "author_slug"
    slug_url_kwarg = "author_slug"
    context_object_name = "page"  # Changed to 'page' to match Wagtail convention
