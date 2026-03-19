import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Horizontal Card",
  argTypes: {
    title: { control: "text" },
    text: { control: "text" },
    image_url: { control: "text" },
    button_url: { control: "text" },
    button_label: { control: "text" },
  },
};

export const Default = (args) => (
  <Pattern template="v3/includes/_horizontal_card.html" context={args} />
);
Default.args = {
  title: "Build anything with Boost",
  text: "Use, modify, and distribute Boost libraries freely. No binary attribution needed.",
  image_url: "/static/img/checker.png",
  button_url: "#",
  button_label: "See license details",
};
