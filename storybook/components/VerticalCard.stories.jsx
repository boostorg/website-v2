import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Vertical Card",
  argTypes: {
    title: { control: "text" },
    text: { control: "text" },
    image_url: { control: "text" },
    primary_button_url: { control: "text" },
    primary_button_label: { control: "text" },
    primary_style: { control: "text" },
  },
};

export const Default = (args) => (
  <Pattern template="v3/includes/_vertical_card.html" context={args} />
);
Default.args = {
  title: "Found a Bug?",
  text: "We rely on developers like you to keep Boost solid. Here's how to report issues that help the whole comm",
  primary_button_url: "www.example.com",
  primary_button_label: "Primary Button",
  primary_style: "secondary-grey",
  image_url: "/static/img/v3/demo_page/Calendar.png",
};
