import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Button Hero",
  argTypes: {
    label: { control: "text" },
    url: { control: "text" },
    style: { control: "select", options: ["primary", "secondary"] },
    icon_name: { control: "text", description: "Icon name from the icon set (e.g. arrow-right, get-help)" },
  },
};

export const Primary = (args) => (
  <Pattern
    template="v3/includes/_button_hero.html"
    context={{
      label: args.label,
      url: args.url,
      style: args.style,
      icon_name: args.icon_name,
    }}
  />
);
Primary.args = {
  label: "Get started",
  url: "#",
  style: "primary",
  icon_name: "arrow-right",
};

export const Secondary = () => (
  <Pattern
    template="v3/includes/_button_hero.html"
    context={{ label: "Learn more", url: "#", style: "secondary" }}
  />
);

export const AsButton = () => (
  <Pattern
    template="v3/includes/_button_hero.html"
    context={{ label: "Submit", style: "primary" }}
  />
);
AsButton.storyName = "As Button (no url)";
