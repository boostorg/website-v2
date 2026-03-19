import React from "react";
import { Pattern } from "storybook-django/src/react";
import { DEMO_EVENTS } from "../mockData";

export default {
  title: "Components/Event Cards",
  argTypes: {
    layout: { control: "select", options: ["vertical", "horizontal"] },
  },
};

export const List = (args) => (
  <Pattern
    template="v3/includes/_event_card.html"
    context={{
      heading: "Upcoming Events",
      heading_url: "#",
      items: DEMO_EVENTS,
      variant: "list",
      layout: args.layout,
      primary_cta_label: "View all events",
      primary_cta_url: "#",
    }}
  />
);
List.args = { layout: "vertical" };

export const Card = (args) => (
  <Pattern
    template="v3/includes/_event_card.html"
    context={{
      heading: "Upcoming Events",
      items: DEMO_EVENTS,
      variant: "card",
      theme: args.theme,
      primary_cta_label: "View all events",
      primary_cta_url: "#",
    }}
  />
);
Card.args = { theme: "default" };
Card.argTypes = {
  layout: { table: { disable: true } },
  theme: {
    control: "select",
    options: ["default", "grey", "yellow", "green", "teal"],
  },
};

export const CardYellow = () => (
  <Pattern
    template="v3/includes/_event_card.html"
    context={{
      heading: "Upcoming Events",
      items: DEMO_EVENTS,
      variant: "card",
      theme: "yellow",
      primary_cta_label: "View all events",
      primary_cta_url: "#",
      secondary_cta_label: "Submit an event",
      secondary_cta_url: "#",
    }}
  />
);
CardYellow.storyName = "Card (Yellow)";

export const CardGreen = () => (
  <Pattern
    template="v3/includes/_event_card.html"
    context={{
      heading: "Upcoming Events",
      items: DEMO_EVENTS,
      variant: "card",
      theme: "green",
      primary_cta_label: "View all events",
      primary_cta_url: "#",
    }}
  />
);
CardGreen.storyName = "Card (Green)";

export const CardTeal = () => (
  <Pattern
    template="v3/includes/_event_card.html"
    context={{
      heading: "Upcoming Events",
      items: DEMO_EVENTS,
      variant: "card",
      theme: "teal",
      primary_cta_label: "View all events",
      primary_cta_url: "#",
    }}
  />
);
CardTeal.storyName = "Card (Teal)";
