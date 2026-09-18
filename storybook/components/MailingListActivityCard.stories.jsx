import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Mailing List Activity Card",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_mailing_list_activity_card.html"
    context={{
      title: "Recent Mailing List Activity",
      primary_button_url: "#",
      mailing_list_items: [
        { date: "2025-09-01", headline: "Boost 1.90.0 release candidate available", url: "#" },
        { date: "2025-08-20", headline: "Call for papers: C++ Now 2026", url: "#" },
        { date: "2025-08-05", headline: "Proposal: new networking library", url: "#" },
      ],
    }}
  />
);
