import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Mailing List Card",
};

export const Default = () => (
  <Pattern template="v3/includes/_mailing_list_card.html" context={{}} />
);
