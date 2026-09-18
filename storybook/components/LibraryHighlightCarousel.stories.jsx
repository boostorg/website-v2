import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Library Highlight Carousel",
};

const DEMO_SLIDES = [
  {
    name: "Boost.Asio",
    category_tags: [{ label: "Networking" }, { label: "I/O" }],
    description:
      "Cross-platform C++ library for network and low-level I/O programming using a consistent asynchronous model.",
    added_in_version: "1.35.0",
    docs_url: "#",
  },
  {
    name: "Boost.Beast",
    category_tags: [{ label: "Networking" }, { label: "HTTP" }],
    description:
      "HTTP and WebSocket built on Boost.Asio, providing low-level building blocks for creating your own libraries.",
    added_in_version: "1.66.0",
    docs_url: "#",
  },
  {
    name: "Boost.JSON",
    category_tags: [{ label: "Parsing" }],
    description:
      "Fast JSON parsing, serialization, and DOM container conforming to RFC 8259.",
    added_in_version: "1.75.0",
    docs_url: "#",
  },
];

export const Default = () => (
  <Pattern
    template="v3/includes/_library_highlight_carousel.html"
    context={{
      carousel_id: "library-highlight-demo",
      slides: DEMO_SLIDES,
    }}
  />
);

export const SingleSlide = () => (
  <Pattern
    template="v3/includes/_library_highlight_carousel.html"
    context={{
      carousel_id: "library-highlight-single",
      slides: DEMO_SLIDES.slice(0, 1),
    }}
  />
);

export const Empty = () => (
  <Pattern
    template="v3/includes/_library_highlight_carousel.html"
    context={{
      carousel_id: "library-highlight-empty",
      slides: [],
    }}
  />
);
