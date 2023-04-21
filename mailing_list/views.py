from django.views.generic import ListView
from .models import MailingListMessage


class MailingListView(ListView):
    model = MailingListMessage
    template_name = "mailing_list/list.html"
    context_object_name = "messages"
    paginate_by = 10

    def get_queryset(self):
        # Retrieve only top-level messages (messages without a parent)
        return MailingListMessage.objects.filter(parent__isnull=True).order_by(
            "-sent_at"
        )
