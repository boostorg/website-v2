import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Content Event Card",
  argTypes: {
    title: { control: "text" },
    description: { control: "text" },
    date: { control: "text" },
    datetime: { control: "text" },
    card_url: { control: "text" },
    event_card_wrapper: { control: "boolean" },
  },
};

export const ListVariant = (args) => (
  <Pattern
    template="v3/includes/_content_event_card_item.html"
    context={{
      title: args.title,
      description: args.description,
      date: args.date,
      datetime: args.datetime,
      card_url: args.card_url,
      card_aria_label: args.title,
      event_card_wrapper: false,
    }}
  />
);
ListVariant.args = {
  title: "Boost 1.90.0 closed for major changes",
  description:
    "Release closed for major code changes. Still open for serious problem fixes and docs changes without release manager review.",
  date: "29/10/25",
  datetime: "29/10/25",
  card_url: "#event-0",
};
ListVariant.storyName = "List Variant";

export const CardVariant = (args) => (
  <Pattern
    template="v3/includes/_content_event_card_item.html"
    context={{
      title: args.title,
      description: args.description,
      date: args.date,
      datetime: args.datetime,
      card_url: args.card_url,
      card_aria_label: args.title,
      event_card_wrapper: true,
    }}
  />
);
CardVariant.args = {
  title: "C++ Now 2025 call for submissions",
  description:
    "C++ Now conference is accepting talk proposals until March 15. Topics include modern C++, Boost libraries, and tooling.",
  date: "12/02/25",
  datetime: "12/02/25",
  card_url: "#event-1",
};
CardVariant.storyName = "Card Variant";
