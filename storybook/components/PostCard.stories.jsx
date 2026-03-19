import React from "react";
import { Pattern } from "storybook-django/src/react";
import { DEMO_POSTS } from "../mockData";

export default {
  title: "Components/Post Card",
  argTypes: {
    variant: { control: "select", options: ["list", "card"] },
    theme: {
      control: "select",
      options: ["default", "grey", "yellow", "green", "teal"],
    },
    layout: { control: "select", options: ["vertical", "horizontal"] },
  },
};

export const List = (args) => (
  <Pattern
    template="v3/includes/_post_card.html"
    context={{
      heading: "Posts from the Boost community",
      heading_url: "#",
      items: DEMO_POSTS,
      variant: "list",
      layout: args.layout,
      primary_cta_label: "View all posts",
      primary_cta_url: "#",
    }}
  />
);
List.args = { layout: "vertical" };
List.argTypes = {
  variant: { table: { disable: true } },
  theme: { table: { disable: true } },
};

export const Card = (args) => (
  <Pattern
    template="v3/includes/_post_card.html"
    context={{
      heading: "Posts from the Boost community",
      heading_url: "#",
      items: DEMO_POSTS,
      variant: "card",
      theme: args.theme,
      primary_cta_label: "View all posts",
      primary_cta_url: "#",
    }}
  />
);
Card.args = { theme: "default" };
Card.argTypes = {
  variant: { table: { disable: true } },
  layout: { table: { disable: true } },
};

export const CardYellow = () => (
  <Pattern
    template="v3/includes/_post_card.html"
    context={{
      heading: "Posts from the Boost community",
      items: DEMO_POSTS,
      variant: "card",
      theme: "yellow",
    }}
  />
);
CardYellow.storyName = "Card (Yellow)";

export const CardGreen = () => (
  <Pattern
    template="v3/includes/_post_card.html"
    context={{
      heading: "Posts from the Boost community",
      items: DEMO_POSTS,
      variant: "card",
      theme: "green",
    }}
  />
);
CardGreen.storyName = "Card (Green)";

export const CardTeal = () => (
  <Pattern
    template="v3/includes/_post_card.html"
    context={{
      heading: "Posts from the Boost community",
      items: DEMO_POSTS,
      variant: "card",
      theme: "teal",
    }}
  />
);
CardTeal.storyName = "Card (Teal)";
