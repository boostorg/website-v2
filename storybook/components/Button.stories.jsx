import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Button",
  argTypes: {
    label: { control: "text", description: "Button text" },
    url: { control: "text", description: "Optional link URL" },
    style: {
      control: "select",
      options: ["primary", "secondary", "green", "yellow", "teal", "error"],
      description: "Button style variant",
    },
    extra_classes: { control: "text", description: "Additional CSS classes" },
  },
};

export const Primary = (args) => (
  <Pattern
    template="v3/includes/_button.html"
    context={{
      label: args.label,
      url: args.url,
      style: args.style,
      extra_classes: args.extra_classes,
    }}
  />
);
Primary.args = {
  label: "Get started",
  url: "#",
  style: "primary",
};

export const Secondary = Primary.bind({});
Secondary.args = {
  label: "Learn more",
  url: "#",
  style: "secondary",
};

export const Green = Primary.bind({});
Green.args = {
  label: "Success",
  url: "#",
  style: "green",
};

export const Yellow = Primary.bind({});
Yellow.args = {
  label: "Warning",
  url: "#",
  style: "yellow",
};

export const Teal = Primary.bind({});
Teal.args = {
  label: "Info",
  url: "#",
  style: "teal",
};

export const Error = Primary.bind({});
Error.args = {
  label: "Delete",
  url: "#",
  style: "error",
};

export const ButtonElement = (args) => (
  <Pattern
    template="v3/includes/_button.html"
    context={{
      label: args.label,
      style: args.style,
    }}
  />
);
ButtonElement.args = {
  label: "Click me",
  style: "primary",
};
ButtonElement.storyName = "Button (no URL)";
