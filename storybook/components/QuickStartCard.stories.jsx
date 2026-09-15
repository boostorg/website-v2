import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Quick Start Card",
  argTypes: {
    heading: { control: "text" },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_quick_start_card.html"
    context={{
      heading: args.heading,
      links: [
        { label: "Getting started", url: "#" },
        { label: "Installation guide", url: "#" },
        { label: "Documentation", url: "#" },
        { label: "Examples", url: "#" },
      ],
    }}
  />
);
Default.args = {
  heading: "Quick Start",
};
