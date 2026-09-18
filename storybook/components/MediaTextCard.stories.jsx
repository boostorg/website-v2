import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Media Text Card",
  argTypes: {
    text: { control: "text" },
    image_url: { control: "text" },
    button_label: { control: "text" },
    button_url: { control: "text" },
  },
};

export const Default = (args) => (
  <Pattern template="v3/includes/_media_text_card.html" context={args} />
);
Default.args = {
  text: "Boost provides free, peer-reviewed, portable C++ source libraries that work well with the C++ Standard Library.",
  image_url: "https://picsum.photos/seed/media-text/480/320",
  button_label: "Learn more",
  button_url: "#",
};

export const NoButton = (args) => (
  <Pattern template="v3/includes/_media_text_card.html" context={args} />
);
NoButton.storyName = "No Button";
NoButton.args = {
  text: "Boost provides free, peer-reviewed, portable C++ source libraries that work well with the C++ Standard Library.",
  image_url: "https://picsum.photos/seed/media-text-2/480/320",
};
