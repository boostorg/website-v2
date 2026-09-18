import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Release Highlights Card",
};

const DEMO_ITEMS = [
  { title: "Boost.JSON", description: "Added streaming parser support for large documents." },
  { title: "Boost.Asio", description: "Improved coroutine cancellation handling." },
  { title: "Boost.Beast", description: "Fixed a WebSocket permessage-deflate edge case." },
];

export const Default = () => (
  <Pattern
    template="v3/includes/_release_highlights_card.html"
    context={{ heading: "What's new in 1.90.0", items: DEMO_ITEMS }}
  />
);

export const WithHeaderAction = () => (
  <Pattern
    template="v3/includes/_release_highlights_card.html"
    context={{
      heading: "What's new in 1.90.0",
      items: DEMO_ITEMS,
      header_action_label: "Release Report",
      header_action_url: "#",
      header_action_icon: "documentation",
    }}
  />
);
WithHeaderAction.storyName = "With Header Action";

export const Empty = () => (
  <Pattern
    template="v3/includes/_release_highlights_card.html"
    context={{ heading: "What's new in 1.90.0", items: [] }}
  />
);
