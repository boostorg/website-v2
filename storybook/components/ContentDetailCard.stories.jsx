import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Content Detail Card",
  argTypes: {
    title: { control: "text" },
    description: { control: "text" },
    icon_name: { control: "text" },
    title_url: { control: "text" },
    cta_label: { control: "text" },
    cta_href: { control: "text" },
  },
};

export const WithIcon = (args) => (
  <Pattern
    template="v3/includes/_content_detail_card_item.html"
    context={args}
  />
);
WithIcon.args = {
  title: "Get help",
  description:
    "Tap into quick answers, networking, and chat with 24,000+ members.",
  icon_name: "bullseye-arrow",
};

export const WithLink = (args) => (
  <Pattern
    template="v3/includes/_content_detail_card_item.html"
    context={args}
  />
);
WithLink.args = {
  title: "Get help",
  description:
    "Tap into quick answers, networking, and chat with 24,000+ members.",
  icon_name: "get-help",
  title_url: "/help",
};

export const WithCTA = (args) => (
  <Pattern
    template="v3/includes/_content_detail_card_item.html"
    context={args}
  />
);
WithCTA.args = {
  title: "Documentation",
  description:
    "Browse library docs, examples, and release notes in one place.",
  icon_name: "link",
  cta_label: "View docs",
  cta_href: "#",
};

export const WithoutIcon = (args) => (
  <Pattern
    template="v3/includes/_content_detail_card_item.html"
    context={args}
  />
);
WithoutIcon.args = {
  title: "Simple card",
  description: "A card with no icon or badge.",
};
