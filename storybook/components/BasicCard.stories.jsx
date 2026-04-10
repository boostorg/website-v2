import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Basic Card",
  argTypes: {
    title: { control: "text", description: "Card heading" },
    text: { control: "text", description: "Card body text" },
    primary_button_url: { control: "text", description: "Primary CTA URL" },
    primary_button_label: { control: "text", description: "Primary CTA label" },
    secondary_button_url: {
      control: "text",
      description: "Secondary CTA URL",
    },
    secondary_button_label: {
      control: "text",
      description: "Secondary CTA label",
    },
  },
};

export const WithTwoButtons = (args) => (
  <Pattern template="v3/includes/_basic_card.html" context={args} />
);
WithTwoButtons.args = {
  title: "Found a Bug?",
  text: "We rely on developers like you to keep Boost solid. Here's how to report issues that help the whole comm",
  primary_button_url: "www.example.com",
  primary_button_label: "Primary Button",
  secondary_button_url: "www.example.com",
  secondary_button_label: "Secondary Button",
};

export const WithOneButton = (args) => (
  <Pattern template="v3/includes/_basic_card.html" context={args} />
);
WithOneButton.args = {
  title: "Found a Bug?",
  text: "We rely on developers like you to keep Boost solid. Here's how to report issues that help the whole comm",
  primary_button_url: "www.example.com",
  primary_button_label: "Primary Button",
};
