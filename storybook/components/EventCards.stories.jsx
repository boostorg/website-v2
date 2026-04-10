import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Event Cards",
};

export const AllVariantsGallery = () => (
  <Pattern template="v3/includes/_event_cards.html" context={{}} />
);
AllVariantsGallery.storyName = "All Variants Gallery";
