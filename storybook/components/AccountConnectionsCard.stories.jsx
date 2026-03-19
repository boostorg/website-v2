import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Account Connections Card",
};

export const MixedState = () => (
  <Pattern
    template="v3/includes/_account_connections_card.html"
    context={{
      connections: [
        {
          platform: "github",
          label: "GitHub",
          connected: true,
          status_text: "Connected",
          action_label: "Manage",
          action_url: "#",
        },
        {
          platform: "google",
          label: "Google",
          connected: false,
          status_text: "Not connected",
          action_label: "Connect",
          action_url: "#",
        },
      ],
    }}
  />
);

export const AllConnected = () => (
  <Pattern
    template="v3/includes/_account_connections_card.html"
    context={{
      connections: [
        {
          platform: "github",
          label: "GitHub",
          connected: true,
          status_text: "Connected",
          action_label: "Manage",
          action_url: "#",
        },
        {
          platform: "google",
          label: "Google",
          connected: true,
          status_text: "Connected",
          action_label: "Manage",
          action_url: "#",
        },
      ],
    }}
  />
);

export const NoneConnected = () => (
  <Pattern
    template="v3/includes/_account_connections_card.html"
    context={{
      connections: [
        {
          platform: "github",
          label: "GitHub",
          connected: false,
          status_text: "Not connected",
          action_label: "Connect",
          action_url: "#",
        },
        {
          platform: "google",
          label: "Google",
          connected: false,
          status_text: "Not connected",
          action_label: "Connect",
          action_url: "#",
        },
      ],
    }}
  />
);
