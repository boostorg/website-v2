from django.urls import path

from .views import TestimonialsIndexView, TestimonialDetailView

urlpatterns = [
    path("", TestimonialsIndexView.as_view(), name="testimonials-index"),
    path(
        "<slug:author_slug>/",
        TestimonialDetailView.as_view(),
        name="testimonial-detail",
    ),
]
