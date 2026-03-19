import React from "react";
import { Pattern } from "storybook-django/src/react";

// Tooltips are part of _button.html via the tp_label / tp_position context variables
// (the button extends _tooltip_v3.html as a base). There is no standalone
// _button_tooltip_v3.html template.

export default {
  title: "Components/Button Tooltip",
  argTypes: {
    tp_label: {
      control: "text",
      description: "Tooltip content text",
    },
    tp_position: {
      control: "select",
      options: ["top", "right", "bottom", "left"],
      description: "Tooltip position relative to the button",
    },
    label: {
      control: "text",
      description: "Button label text",
    },
  },
};

export const Top = (args) => (
  <Pattern
    template="v3/includes/_button.html"
    context={{
      label: args.label,
      tp_label: args.tp_label,
      tp_position: "top",
    }}
  />
);
Top.args = { label: "Help", tp_label: "Opens in a new window" };

export const Right = (args) => (
  <Pattern
    template="v3/includes/_button.html"
    context={{
      label: args.label,
      tp_label: args.tp_label,
      tp_position: "right",
    }}
  />
);
Right.args = { label: "Help", tp_label: "Opens in a new window" };

export const Bottom = (args) => (
  <Pattern
    template="v3/includes/_button.html"
    context={{
      label: args.label,
      tp_label: args.tp_label,
      tp_position: "bottom",
    }}
  />
);
Bottom.args = { label: "Help", tp_label: "Opens in a new window" };

export const Left = (args) => (
  <Pattern
    template="v3/includes/_button.html"
    context={{
      label: args.label,
      tp_label: args.tp_label,
      tp_position: "left",
    }}
  />
);
Left.args = { label: "Help", tp_label: "Opens in a new window" };

export const Interactive = (args) => (
  <Pattern
    template="v3/includes/_button.html"
    context={{
      label: args.label,
      tp_label: args.tp_label,
      tp_position: args.tp_position,
    }}
  />
);
Interactive.args = {
  label: "Help",
  tp_label: "More information about this action",
  tp_position: "bottom",
};
Interactive.storyName = "Interactive (controls)";

export const LongLabel = () => (
  <Pattern
    template="v3/includes/_button.html"
    context={{
      label: "Info",
      tp_label: "This tooltip has a longer explanatory message that wraps across lines",
      tp_position: "bottom",
    }}
  />
);
LongLabel.storyName = "Long label";

export const SecondaryButton = () => (
  <Pattern
    template="v3/includes/_button.html"
    context={{
      label: "Learn more",
      style: "secondary",
      tp_label: "Opens documentation",
      tp_position: "top",
    }}
  />
);
SecondaryButton.storyName = "Secondary button with tooltip";
