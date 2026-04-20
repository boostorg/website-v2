import React from "react";
import { Pattern } from "storybook-django/src/react";

const sampleDeps = [
  { name: "Asio", url: "#" },
  { name: "Beast", url: "#" },
  { name: "Filesystem", url: "#" },
  { name: "JSON", url: "#" },
];

export default {
  title: "Components/Dependencies Card",
};

export const WithDependencies = () => (
  <Pattern
    template="v3/includes/_dependencies_card.html"
    context={{ dependencies: sampleDeps }}
  />
);
WithDependencies.storyName = "With Dependencies";

export const Empty = () => (
  <Pattern
    template="v3/includes/_dependencies_card.html"
    context={{ dependencies: [] }}
  />
);

export const CustomHeading = () => (
  <Pattern
    template="v3/includes/_dependencies_card.html"
    context={{ heading: "Depends on", dependencies: sampleDeps }}
  />
);
CustomHeading.storyName = "Custom Heading";
