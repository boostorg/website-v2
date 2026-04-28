import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Dialog",
  argTypes: {
    dialog_id: { control: "text" },
    title: { control: "text" },
    description: { control: "text" },
    primary_label: { control: "text" },
    secondary_label: { control: "text" },
  },
};

export const WithDescription = (args) => (
  <div>
    <button
      className="btn btn-primary"
      onClick={(e) => {
        e.preventDefault();
        window.location.hash = args.dialog_id;
      }}
    >
      Open dialog
    </button>
    <Pattern
      template="v3/includes/_dialog.html"
      context={{
        dialog_id: args.dialog_id,
        title: args.title,
        description: args.description,
        primary_label: args.primary_label,
        secondary_label: args.secondary_label,
        primary_url: "#_",
        secondary_url: "#_",
      }}
    />
  </div>
);
WithDescription.args = {
  dialog_id: "demo-dialog-with-desc",
  title: "Title of Dialog",
  description: "Description that can go inside of Dialog",
  primary_label: "Button",
  secondary_label: "Button",
};

export const WithoutDescription = (args) => (
  <div>
    <button
      className="btn btn-primary"
      onClick={(e) => {
        e.preventDefault();
        window.location.hash = args.dialog_id;
      }}
    >
      Open dialog
    </button>
    <Pattern
      template="v3/includes/_dialog.html"
      context={{
        dialog_id: args.dialog_id,
        title: args.title,
        primary_label: args.primary_label,
        secondary_label: args.secondary_label,
        primary_url: "#_",
        secondary_url: "#_",
      }}
    />
  </div>
);
WithoutDescription.args = {
  dialog_id: "demo-dialog-no-desc",
  title: "Confirm Action",
  primary_label: "Confirm",
  secondary_label: "Cancel",
};
