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

export const ComboMultiSelect = () => (
  <Pattern
    template="v3/includes/_field_combo_multi.html"
    context={{
      name: "ex_combo_multi",
      label: "Combo multi-select (searchable)",
      placeholder: "Search and select...",
      options_json: JSON.stringify([
        { value: "algorithms", label: "Algorithms" },
        { value: "containers", label: "Containers" },
        { value: "io", label: "I/O" },
        { value: "math", label: "Math & Numerics" },
        { value: "networking", label: "Networking" },
        { value: "string", label: "String & Text" },
      ]),
    }}
  />
);

export const Dropdown = () => (
  <Pattern
    template="v3/includes/_field_dropdown.html"
    context={{
      name: "ex_version",
      label: "Boost Version",
      placeholder: "Select a version...",
      options: [
        ["1.88.0", "Boost 1.88.0"],
        ["1.87.0", "Boost 1.87.0"],
        ["1.86.0", "Boost 1.86.0"],
        ["1.85.0", "Boost 1.85.0"],
      ],
    }}
  />
);

export const DropdownWithSelection = () => (
  <Pattern
    template="v3/includes/_field_dropdown.html"
    context={{
      name: "ex_version_selected",
      label: "Boost Version",
      options: [
        ["1.88.0", "Boost 1.88.0"],
        ["1.87.0", "Boost 1.87.0"],
        ["1.86.0", "Boost 1.86.0"],
      ],
      selected: "1.87.0",
    }}
  />
);
DropdownWithSelection.storyName = "Dropdown (pre-selected)";

export const DropdownWithError = () => (
  <Pattern
    template="v3/includes/_field_dropdown.html"
    context={{
      name: "ex_version_error",
      label: "Boost Version",
      placeholder: "Select a version...",
      options: [
        ["1.88.0", "Boost 1.88.0"],
        ["1.87.0", "Boost 1.87.0"],
      ],
      error: "Please select a version.",
    }}
  />
);
DropdownWithError.storyName = "Dropdown (error state)";
