import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Code Block",
  argTypes: {
    variant: { control: "select", options: ["standalone", "white-bg", "grey-bg"] },
    language: { control: "text" },
  },
};

const CODE_HELLO = `#include <iostream>
int main()
{
    std::cout << "Hello, Boost.";
}`;

export const Default = (args) => (
  <Pattern
    template="v3/includes/_code_block.html"
    context={{ code: CODE_HELLO, variant: args.variant, language: args.language }}
  />
);
Default.args = {
  variant: "standalone",
  language: "cpp",
};

export const GreyBackground = (args) => (
  <Pattern
    template="v3/includes/_code_block.html"
    context={{ code: CODE_HELLO, variant: args.variant, language: args.language }}
  />
);
GreyBackground.storyName = "Grey Background";
GreyBackground.args = {
  variant: "grey-bg",
  language: "cpp",
};
