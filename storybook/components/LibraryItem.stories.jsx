import React from "react";
import { Pattern } from "storybook-django/src/react";
import { DEMO_AUTHOR } from "../mockData";

const DEMO_CATEGORIES = [
  { label: "Networking", slug: "networking", variant: "teal" },
  { label: "I/O", slug: "io", variant: "neutral" },
];

const DEMO_LIBRARY = {
  library_name: "Boost.Asio",
  library_url: "#",
  description:
    "Portable networking and other low-level I/O, including sockets, timers, hostname resolution and socket iostreams.",
  categories: DEMO_CATEGORIES,
  cpp_version: "11",
  author: DEMO_AUTHOR,
  doc_url: "#",
};

export default {
  title: "Components/Library Item",
  argTypes: {
    variant: { control: "select", options: ["list", "card"] },
  },
};

export const ListVariant = (args) => (
  <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
    <Pattern
      template="v3/includes/_library_item.html"
      context={{ ...DEMO_LIBRARY, variant: "list" }}
    />
  </ul>
);
ListVariant.storyName = "List variant";

export const CardVariant = () => (
  <Pattern
    template="v3/includes/_library_item.html"
    context={{ ...DEMO_LIBRARY, variant: "card" }}
  />
);
CardVariant.storyName = "Card variant";

export const MultipleCategories = () => (
  <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
    <Pattern
      template="v3/includes/_library_item.html"
      context={{
        ...DEMO_LIBRARY,
        library_name: "Boost.Beast",
        description:
          "HTTP and WebSocket built on Boost.Asio in C++11. Provides low-level HTTP/1 and WebSocket protocol handling.",
        categories: [
          { label: "Networking", slug: "networking", variant: "teal" },
          { label: "HTTP", slug: "http", variant: "neutral" },
          { label: "WebSocket", slug: "websocket", variant: "neutral" },
        ],
        variant: "list",
      }}
    />
  </ul>
);
MultipleCategories.storyName = "Multiple categories";

export const NoProfileLink = () => (
  <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
    <Pattern
      template="v3/includes/_library_item.html"
      context={{
        ...DEMO_LIBRARY,
        author: { name: "Vinnie Falco", role: "Author & Maintainer" },
        variant: "list",
      }}
    />
  </ul>
);
NoProfileLink.storyName = "Author without profile link";
