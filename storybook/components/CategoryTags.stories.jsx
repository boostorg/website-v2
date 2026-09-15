import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Category Tags",
};

export const AllVariants = () => (
  <Pattern
    template="v3/includes/_category_cards.html"
    context={{ show_version_tags: true }}
  />
);
AllVariants.storyName = "All Variants";
