import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Inline Card",
  argTypes: {
    title: { control: "text" },
    text: { control: "text" },
    image_url: { control: "text" },
    image_alt: { control: "text" },
    button_url: { control: "text" },
    button_label: { control: "text" },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_inline_card.html"
    context={{
      title: args.title,
      text: args.text,
      image_url: args.image_url,
      image_alt: args.image_alt,
      button_url: args.button_url,
      button_label: args.button_label,
    }}
  />
);
Default.args = {
  title: "Boost C++ Libraries",
  text: "Boost provides free peer-reviewed portable C++ source libraries. We emphasize libraries that work well with the C++ Standard Library.",
  image_url: "https://picsum.photos/seed/boost/320/320",
  image_alt: "Boost C++ Libraries",
  button_url: "#",
  button_label: "Learn more",
};
