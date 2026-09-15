import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Badge Button",
  argTypes: {
    name: { control: "text" },
    value: { control: "text" },
    icon: { control: "text" },
    icon_alt: { control: "text" },
    radio_checked: { control: "boolean" },
  },
};

export const Default = (args) => (
  <Pattern template="v3/includes/_badge_button.html" context={args} />
);
Default.args = {
  name: "badge-select-demo",
  value: "gold",
  icon: "badge-tier-3",
  icon_alt: "Gold badge",
  radio_checked: false,
};

export const Checked = (args) => (
  <Pattern template="v3/includes/_badge_button.html" context={args} />
);
Checked.args = {
  name: "badge-select-demo-checked",
  value: "gold",
  icon: "badge-tier-3",
  icon_alt: "Gold badge",
  radio_checked: true,
};
