import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Wysiwyg Editor",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_wysiwyg_editor.html"
    context={{
      textarea_id: "id_content",
      textarea_name: "content",
      value: "Write something about your contribution here.",
      help_text: "Markdown is supported.",
    }}
  />
);

export const BioPreset = () => (
  <Pattern
    template="v3/includes/_wysiwyg_editor.html"
    context={{
      textarea_id: "id_bio",
      textarea_name: "bio",
      preset: "bio",
      maxlength: 500,
    }}
  />
);
BioPreset.storyName = "Bio Preset";
