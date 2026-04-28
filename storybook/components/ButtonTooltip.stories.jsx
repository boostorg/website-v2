import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Button Tooltip",
  argTypes: {
    label: { control: "text", description: "Tooltip content text" },
    position: {
      control: "select",
      options: ["top", "right", "bottom", "left"],
      description: "Tooltip position",
    },
    button_text: {
      control: "text",
      description: "Optional text on the trigger button",
    },
  },
};

export const Top = (args) => (
  <Pattern
    template="v3/includes/_button_tooltip_v3.html"
    context={{
      label: args.label,
      position: args.position,
      button_text: args.button_text,
    }}
  />
);
Top.args = {
  label: "Top",
  position: "top",
  button_text: "Help",
};

export const Right = Top.bind({});
Right.args = {
  label: "Right",
  position: "right",
  button_text: "Help",
};

export const Bottom = Top.bind({});
Bottom.args = {
  label: "Bottom",
  position: "bottom",
  button_text: "Help",
};

export const Left = Top.bind({});
Left.args = {
  label: "Left",
  position: "left",
  button_text: "Help",
};

export const LongLabel = Top.bind({});
LongLabel.args = {
  label: "More information here",
  position: "bottom",
  button_text: "Info",
};

export const IconOnly = (args) => (
  <Pattern
    template="v3/includes/_button_tooltip_v3.html"
    context={{
      label: args.label,
      position: args.position,
    }}
  />
);
IconOnly.args = {
  label: "Icon only tooltip",
  position: "bottom",
};
IconOnly.storyName = "Icon Only";
