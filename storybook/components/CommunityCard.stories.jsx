import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Community Card",
};

const DEMO_ITEMS = [
  {
    title: "Slack",
    description: "Chat with the community in real time.",
    cta_url: "#",
    cta_label: "Join us on Slack",
    icon_name: "message",
  },
  {
    title: "Mailing Lists",
    description: "Follow announcements and discussions by email.",
    cta_url: "#",
    cta_label: "Subscribe",
  },
  {
    title: "GitHub",
    description: "Browse issues, pull requests and source code.",
    cta_url: "#",
    cta_label: "Visit GitHub",
    icon_name: "github-logo",
  },
];

export const List = () => (
  <Pattern
    template="v3/includes/_community_card.html"
    context={{
      heading: "Get involved",
      items: DEMO_ITEMS,
    }}
  />
);

export const CardVariant = () => (
  <Pattern
    template="v3/includes/_community_card.html"
    context={{
      heading: "Get involved",
      items: DEMO_ITEMS,
      variant: "card",
      theme: "teal",
      primary_cta_label: "See all ways to connect",
      primary_cta_url: "#",
    }}
  />
);
CardVariant.storyName = "Card Variant";
