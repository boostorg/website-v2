import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Empty State",
  argTypes: {
    title: { control: "text" },
    description: { control: "text" },
    cta_label: { control: "text" },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_empty_state.html"
    context={{
      title: args.title,
      description: args.description,
    }}
  />
);
Default.args = {
  title: "No results, please search again...",
  description: "Try a shorter keyword, or check the spelling.",
};

export const WithCallToAction = (args) => (
  <Pattern
    template="v3/includes/_empty_state.html"
    context={{
      title: args.title,
      description: args.description,
      cta_label: args.cta_label,
      cta_url: "#",
    }}
  />
);
WithCallToAction.args = {
  title: "No libraries found",
  description: "Try adjusting your filters, or explore the full catalogue.",
  cta_label: "Browse all libraries",
};

export const Inset = () => (
  <Pattern
    template="v3/includes/_empty_state.html"
    context={{
      title: "Nothing to show yet",
      description: "Contributions will appear here once available.",
      variant: "inset",
    }}
  />
);
