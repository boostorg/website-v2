import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Library Discovery Card",
};

const DEMO_ITEMS = [
  {
    name: "Boost.Asio",
    url: "#",
    description: "Cross-platform networking and low-level I/O programming.",
    categories: ["Networking", "I/O"],
    cpp_version: "C++ 11",
  },
  {
    name: "Boost.JSON",
    url: "#",
    description: "Fast JSON parsing, serialization, and DOM container.",
    categories: ["Parsing"],
    cpp_version: "C++ 11",
  },
  {
    name: "Boost.Spirit",
    description: "Parser and output generation framework.",
    categories: ["Parsing", "Generation"],
  },
];

export const List = () => (
  <Pattern
    template="v3/includes/_library_discovery_card.html"
    context={{
      heading: "Discover a library that meets your needs",
      items: DEMO_ITEMS,
      primary_cta_label: "See all libraries",
      primary_cta_url: "#",
    }}
  />
);

export const CardVariant = () => (
  <Pattern
    template="v3/includes/_library_discovery_card.html"
    context={{
      heading: "Discover a library that meets your needs",
      items: DEMO_ITEMS,
      variant: "card",
      theme: "green",
      primary_cta_label: "See all libraries",
      primary_cta_url: "#",
    }}
  />
);
CardVariant.storyName = "Card Variant";
