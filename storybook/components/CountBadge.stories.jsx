import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Count Badge",
  argTypes: {
    value: { control: "text" },
    size: { control: "select", options: ["small", "medium", "large"] },
  },
};

export const Default = (args) => (
  <Pattern template="v3/includes/_count_badge.html" context={args} />
);
Default.args = {
  value: 7,
  size: "medium",
};

export const CompactCount = (args) => (
  <Pattern template="v3/includes/_count_badge.html" context={args} />
);
CompactCount.storyName = "Compact Count (2.3k)";
CompactCount.args = {
  value: 2300,
  size: "medium",
};
