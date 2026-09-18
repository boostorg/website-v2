import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Search Card",
  argTypes: {
    heading: { control: "text" },
    action_url: { control: "text" },
    placeholder: { control: "text" },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_search_card.html"
    context={args}
  />
);
Default.args = {
  heading: "What are you trying to find?",
  action_url: "#",
  placeholder: "Search libraries, docs, examples",
  popular_terms: [
    { label: "Networking" },
    { label: "Math" },
    { label: "Data processing" },
    { label: "Concurrency" },
    { label: "File systems" },
    { label: "Testing" },
  ],
};

export const WithoutPopularTerms = (args) => (
  <Pattern
    template="v3/includes/_search_card.html"
    context={args}
  />
);
WithoutPopularTerms.args = {
  heading: "Search documentation",
  action_url: "#",
};
