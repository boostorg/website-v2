import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Form Inputs",
};

export const TextField = (args) => (
  <Pattern
    template="v3/includes/_field_text.html"
    context={{
      name: args.name,
      label: args.label,
      placeholder: args.placeholder,
    }}
  />
);
TextField.args = {
  name: "ex_basic",
  label: "Text field",
  placeholder: "Enter text...",
};
TextField.argTypes = {
  name: { control: "text" },
  label: { control: "text" },
  placeholder: { control: "text" },
};

export const WithIcon = () => (
  <Pattern
    template="v3/includes/_field_text.html"
    context={{
      name: "ex_search",
      label: "With icon",
      placeholder: "Search...",
      icon_left: "search",
    }}
  />
);

export const ErrorState = () => (
  <Pattern
    template="v3/includes/_field_text.html"
    context={{
      name: "ex_error",
      label: "Error state",
      placeholder: "Enter value",
      error: "This field is required.",
    }}
  />
);

export const Checkbox = () => (
  <Pattern
    template="v3/includes/_field_checkbox.html"
    context={{
      name: "ex_agree",
      label: "I agree to the terms and conditions",
    }}
  />
);

export const ComboBox = () => (
  <Pattern
    template="v3/includes/_field_combo.html"
    context={{
      name: "ex_library",
      label: "Combo (searchable)",
      placeholder: "Search libraries...",
      options_json: JSON.stringify([
        { value: "asio", label: "Asio" },
        { value: "beast", label: "Beast" },
        { value: "filesystem", label: "Filesystem" },
        { value: "json", label: "JSON" },
        { value: "spirit", label: "Spirit" },
      ]),
    }}
  />
);

export const MultiSelect = () => (
  <Pattern
    template="v3/includes/_field_multiselect.html"
    context={{
      name: "ex_categories",
      label: "Multi-select",
      placeholder: "Select categories...",
      options_json: JSON.stringify([
        { value: "algorithms", label: "Algorithms" },
        { value: "containers", label: "Containers" },
        { value: "io", label: "I/O" },
        { value: "math", label: "Math & Numerics" },
        { value: "networking", label: "Networking" },
      ]),
    }}
  />
);
