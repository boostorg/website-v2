import React from "react";
import { Pattern } from "storybook-django/src/react";

const DEMO_ITEMS = [
  {
    title: "Join the mailing list",
    url: "#",
    description: "Stay up to date with Boost releases, proposals, and discussions.",
    icon_name: "mail",
  },
  {
    title: "Join us on Slack",
    url: "#",
    description: "Real-time chat with Boost contributors and library authors.",
    icon_name: "slack",
  },
  {
    title: "Contribute on GitHub",
    url: "#",
    description: "Open issues, submit pull requests, and review library changes.",
    icon_name: "github",
  },
];

export default {
  title: "Components/Join Card",
  argTypes: {
    theme: {
      control: "select",
      options: ["default", "grey", "yellow", "green", "teal"],
    },
  },
};

export const List = () => (
  <Pattern
    template="v3/includes/_join_card.html"
    context={{
      heading: "Join the Boost community",
      items: DEMO_ITEMS,
      variant: "list",
    }}
  />
);

export const Card = (args) => (
  <Pattern
    template="v3/includes/_join_card.html"
    context={{
      heading: "Join the Boost community",
      items: DEMO_ITEMS,
      variant: "card",
      theme: args.theme,
      primary_cta_label: "Explore the community",
      primary_cta_url: "#",
    }}
  />
);
Card.args = { theme: "default" };
Card.argTypes = {
  theme: {
    control: "select",
    options: ["default", "grey", "yellow", "green", "teal"],
  },
};

export const CardYellow = () => (
  <Pattern
    template="v3/includes/_join_card.html"
    context={{
      heading: "Join the Boost community",
      items: DEMO_ITEMS,
      variant: "card",
      theme: "yellow",
      primary_cta_label: "Explore the community",
      primary_cta_url: "#",
    }}
  />
);
CardYellow.storyName = "Card (Yellow)";

export const CardTeal = () => (
  <Pattern
    template="v3/includes/_join_card.html"
    context={{
      heading: "Join the Boost community",
      items: DEMO_ITEMS,
      variant: "card",
      theme: "teal",
      primary_cta_label: "Explore the community",
      primary_cta_url: "#",
    }}
  />
);
CardTeal.storyName = "Card (Teal)";
