from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)

from .models import News
from .forms import NewsForm


class NewsListView(ListView):
    model = News
    template_name = "news/list.html"
    ordering = ["-created"]
    paginate_by = 10

    # ToDo: override queryset to get only published news


class NewsDetailView(DetailView):
    model = News
    template_name = "news/detail.html"


class NewsCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = News
    form_class = NewsForm
    template_name = "news/update.html"
    success_url = reverse_lazy("news")

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def test_func(self):
        return True  # self.request.user.groups.filter(name="editors").exists()


class NewsUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = News
    form_class = NewsForm
    template_name = "news/update.html"

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def test_func(self):
        news = self.get_object()
        return self.request.user == news.author


class NewsDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = News
    template_name = "news/confirm_delete.html"
    success_url = reverse_lazy("news")

    def test_func(self):
        news = self.get_object()
        return self.request.user == news.author
