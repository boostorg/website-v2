from django.views.generic import DetailView, ListView
from .models import MailingListMessage


class MailingListView(ListView):
    model = MailingListMessage
    template_name = "mailing_list/list.html"
    context_object_name = "messages"
    paginate_by = 10

    def get_queryset(self):
        return MailingListMessage.objects.filter(parent__isnull=True).order_by(
            "-sent_at"
        )


class MailingListDetailView(DetailView):
    model = MailingListMessage
    template_name = "mailing_list/detail.html"
    context_object_name = "message"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["replies"] = self.object.replies.order_by("sent_at")
        return context
