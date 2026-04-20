import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Learn Card",
  argTypes: {
    title: { control: "text" },
    text: { control: "text" },
    label: { control: "text", description: "CTA button label" },
    url: { control: "text", description: "CTA button URL" },
    image_src: { control: "text" },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_learn_card.html"
    context={{
      title: args.title,
      text: args.text,
      links: [
        { label: "Explore common use cases", url: "https://www.example.com" },
        { label: "Build with CMake", url: "https://www.example.com" },
        { label: "Visit the FAQ", url: "https://www.example.com" },
      ],
      url: args.url,
      label: args.label,
      image_src: args.image_src,
    }}
  />
);
Default.args = {
  title: "I want to learn:",
  text: "How to install Boost, use its libraries, build projects, and get help when you need it.",
  label: "Learn more about Boost",
  url: "https://www.example.com",
  image_src: "/static/img/v3/examples/Learn Card Image.png",
};
