import React from "react";
import { Pattern } from "storybook-django/src/react";

const sampleMarkdown = `Boost provides **free** peer-reviewed portable C++ source libraries.

## Features

- Header-only and compiled libraries
- Works with any C++ compiler supporting C++03 and later
- Used by thousands of open source and commercial projects

\`\`\`cpp
#include <boost/filesystem.hpp>

namespace fs = boost::filesystem;
fs::path p("/usr/local/include");
\`\`\`

See the [documentation](#) for details.`;

export default {
  title: "Components/Markdown Card",
  argTypes: {
    title: { control: "text" },
    button_label: { control: "text" },
    button_url: { control: "text" },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_markdown_card.html"
    context={{
      title: args.title,
      markdown: sampleMarkdown,
      button_url: args.button_url,
      button_label: args.button_label,
    }}
  />
);
Default.args = {
  title: "About Boost",
  button_url: "#",
  button_label: "Read the docs",
};

export const NoCTA = () => (
  <Pattern
    template="v3/includes/_markdown_card.html"
    context={{
      title: "Release Notes",
      markdown: sampleMarkdown,
    }}
  />
);
NoCTA.storyName = "No CTA";
