import React from "react";
import { Pattern } from "storybook-django/src/react";

const categoryOptions = [
  { label: "All", value: "all" },
  { label: "News", value: "news" },
  { label: "Releases", value: "releases" },
  { label: "Community", value: "community" },
  { label: "Events", value: "events" },
];

export default {
  title: "Components/Post Filter",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_post_filter.html"
    context={{
      options: categoryOptions,
      filter_name: "category",
      default: "all",
    }}
  />
);

export const WithPreselection = () => (
  <Pattern
    template="v3/includes/_post_filter.html"
    context={{
      options: categoryOptions,
      filter_name: "category",
      default: "releases",
    }}
  />
);
WithPreselection.storyName = "With Pre-selected Option";
