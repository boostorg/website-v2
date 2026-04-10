import React from "react";
import { Pattern } from "storybook-django/src/react";

const sampleEvents = [
  {
    title: "Boost 1.90.0 closed for major changes",
    description: "Release closed for major code changes. Still open for serious problem fixes and docs changes without release manager review.",
    date: "29/10/25",
    datetime: "2025-10-29",
    card_url: "#",
    card_aria_label: "Boost 1.90.0 closed for major changes",
  },
  {
    title: "C++ Now 2025 call for submissions",
    description: "C++ Now conference is accepting talk proposals until March 15.",
    date: "12/02/25",
    datetime: "2025-02-12",
    card_url: "#",
    card_aria_label: "C++ Now 2025 call for submissions",
  },
  {
    title: "Boost 1.89.0 released",
    description: "Boost 1.89.0 is available with updates to Asio, Beast, and several other libraries.",
    date: "15/01/25",
    datetime: "2025-01-15",
    card_url: "#",
    card_aria_label: "Boost 1.89.0 released",
  },
];

export default {
  title: "Components/Event Cards Section",
  argTypes: {
    variant: {
      control: "select",
      options: ["white", "grey", "yellow", "green", "teal"],
    },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_event_cards_section.html"
    context={{
      section_heading: "Upcoming Events",
      event_list: sampleEvents,
      variant: args.variant,
      primary_btn_text: "View all events",
      primary_btn_url: "#",
    }}
  />
);
Default.args = { variant: "white" };

export const Yellow = () => (
  <Pattern
    template="v3/includes/_event_cards_section.html"
    context={{
      section_heading: "Upcoming Events",
      event_list: sampleEvents,
      variant: "yellow",
      primary_btn_text: "View all events",
      primary_btn_url: "#",
      secondary_btn_text: "Submit an event",
      secondary_btn_url: "#",
    }}
  />
);

export const Green = () => (
  <Pattern
    template="v3/includes/_event_cards_section.html"
    context={{
      section_heading: "Upcoming Events",
      event_list: sampleEvents,
      variant: "green",
      primary_btn_text: "View all events",
      primary_btn_url: "#",
    }}
  />
);

export const Teal = () => (
  <Pattern
    template="v3/includes/_event_cards_section.html"
    context={{
      section_heading: "Upcoming Events",
      event_list: sampleEvents,
      variant: "teal",
      primary_btn_text: "View all events",
      primary_btn_url: "#",
    }}
  />
);
