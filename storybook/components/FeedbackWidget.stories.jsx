import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Feedback Widget",
};

const FEEDBACK_TYPE_OPTIONS = [
  ["bug", "Bug"],
  ["suggestion", "Suggestion"],
  ["question", "Question"],
  ["usability", "Usability"],
  ["incorrect_information", "Incorrect information"],
  ["other", "Other"],
];

export const Default = () => (
  <Pattern
    template="v3/includes/_feedback_widget.html"
    context={{
      feedback_type_options: FEEDBACK_TYPE_OPTIONS,
      image_max_bytes: 2 * 1024 * 1024,
      message_max_length: 4000,
    }}
  />
);
