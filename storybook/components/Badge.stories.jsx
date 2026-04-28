import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Badge",
  argTypes: {
    value: { control: "text", description: "Number or text to display. Numbers ≥ 1000 are shown compact (e.g. 2.3k)." },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_badge_v3.html"
    context={{ value: args.value }}
  />
);
Default.args = { value: 5 };

export const LargeNumber = () => (
  <Pattern template="v3/includes/_badge_v3.html" context={{ value: 2347 }} />
);
LargeNumber.storyName = "Large Number (compact)";
