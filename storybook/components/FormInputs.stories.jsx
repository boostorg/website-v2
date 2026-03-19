import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Form Inputs",
};

// --- Text fields ---

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

export const Textarea = () => (
  <Pattern
    template="v3/includes/_field_textarea.html"
    context={{
      name: "ex_content",
      label: "Content",
      placeholder: "Write something...",
      rows: 4,
    }}
  />
);

export const TextareaError = () => (
  <Pattern
    template="v3/includes/_field_textarea.html"
    context={{
      name: "ex_content_error",
      label: "Content",
      placeholder: "Write something...",
      error: "Content cannot be empty.",
    }}
  />
);
TextareaError.storyName = "Textarea (error state)";

// --- Password ---

export const Password = () => (
  <Pattern
    template="v3/includes/_field_password.html"
    context={{
      name: "ex_password",
      label: "Password*",
      placeholder: "Enter password",
      password_rules: [
        { label: "At least 8 characters", type: "min_length", value: 8 },
        {
          label: "At least one uppercase letter",
          type: "regex",
          value: "[A-Z]",
        },
        { label: "At least one number", type: "regex", value: "[0-9]" },
      ],
    }}
  />
);

export const PasswordWithError = () => (
  <Pattern
    template="v3/includes/_field_password.html"
    context={{
      name: "ex_password_err",
      label: "Password*",
      error: "Password does not meet requirements.",
    }}
  />
);
PasswordWithError.storyName = "Password (error state)";

// --- File input ---

export const FileInput = () => (
  <Pattern
    template="v3/includes/_field_file.html"
    context={{
      name: "ex_file",
      label: "Upload file",
      help_text: "Accepted formats: PNG, JPEG, PDF. Max 5 MB.",
    }}
  />
);

export const FileInputWithPreview = () => (
  <Pattern
    template="v3/includes/_field_file.html"
    context={{
      name: "ex_avatar",
      label: "Profile image",
      accept: "image/png,image/jpeg",
      preview: true,
      help_text: "PNG or JPEG, max 1 MB.",
    }}
  />
);
FileInputWithPreview.storyName = "File Input (with image preview)";

// --- DateTime ---

export const DateTimeInput = () => (
  <Pattern
    template="v3/includes/_field_datetime.html"
    context={{
      name: "ex_publish_at",
      label: "Publish date",
      help_text: "Must be a future date and time.",
    }}
  />
);
DateTimeInput.storyName = "DateTime Input";

// --- Select / combo fields ---

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
