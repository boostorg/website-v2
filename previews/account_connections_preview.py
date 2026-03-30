from django_lookbook.preview import LookbookPreview
from django.template.loader import render_to_string


class AccountConnectionsCardPreview(LookbookPreview):

    def mixed(self, **kwargs):
        """
        Account connections card with one connected and one not connected.

        Template: `v3/includes/_account_connections_card.html`

        | Variable | Required | Description |
        |---|---|---|
        | `heading` | No | Card heading. Default: "Account connections" |
        | `connections` | Yes | List of connection dicts with: platform, label, connected, status_text, action_label, action_url |
        """
        return render_to_string(
            "v3/includes/_account_connections_card.html",
            {
                "connections": [
                    {
                        "platform": "github",
                        "label": "GitHub",
                        "connected": True,
                        "status_text": "Connected",
                        "action_label": "Manage",
                        "action_url": "#",
                    },
                    {
                        "platform": "google",
                        "label": "Google",
                        "connected": False,
                        "status_text": "Not connected",
                        "action_label": "Connect",
                        "action_url": "#",
                    },
                ],
            },
        )

    def all_connected(self, **kwargs):
        """
        Account connections card with all accounts connected.
        """
        return render_to_string(
            "v3/includes/_account_connections_card.html",
            {
                "connections": [
                    {
                        "platform": "github",
                        "label": "GitHub",
                        "connected": True,
                        "status_text": "Connected",
                        "action_label": "Manage",
                        "action_url": "#",
                    },
                    {
                        "platform": "google",
                        "label": "Google",
                        "connected": True,
                        "status_text": "Connected",
                        "action_label": "Manage",
                        "action_url": "#",
                    },
                ],
            },
        )

    def none_connected(self, **kwargs):
        """
        Account connections card with no accounts connected.
        """
        return render_to_string(
            "v3/includes/_account_connections_card.html",
            {
                "connections": [
                    {
                        "platform": "github",
                        "label": "GitHub",
                        "connected": False,
                        "status_text": "Not connected",
                        "action_label": "Connect",
                        "action_url": "#",
                    },
                    {
                        "platform": "google",
                        "label": "Google",
                        "connected": False,
                        "status_text": "Not connected",
                        "action_label": "Connect",
                        "action_url": "#",
                    },
                ],
            },
        )
