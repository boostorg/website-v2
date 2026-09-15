import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Code Block Card",
};

const CODE_INSTALL = `brew install openssl

export OPENSSL_ROOT=$(brew --prefix openssl)`;

export const Default = () => (
  <Pattern
    template="v3/includes/_code_block_card.html"
    context={{
      heading: "Install with Homebrew",
      description: "Get up and running on macOS in a couple of commands.",
      code: CODE_INSTALL,
      language: "bash",
    }}
  />
);

export const WithButton = () => (
  <Pattern
    template="v3/includes/_code_block_card.html"
    context={{
      card_variant: "teal",
      heading: "Install with Homebrew",
      description: "Get up and running on macOS in a couple of commands.",
      code: CODE_INSTALL,
      language: "bash",
      button_text: "View all install methods",
      button_url: "#",
    }}
  />
);
WithButton.storyName = "With Button";
