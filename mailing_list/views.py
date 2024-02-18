#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
from django.views.generic import DetailView, ListView
from .models import MailingListMessage


class MailingListView(ListView):
    model = MailingListMessage
    template_name = "mailing_list/list.html"
    context_object_name = "objects"
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
