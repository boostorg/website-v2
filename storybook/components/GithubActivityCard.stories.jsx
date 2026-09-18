import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Github Activity Card",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_github_activity_card.html"
    context={{
      data: {
        refreshing: false,
        title: "Recent GitHub Activity",
        markdown_text:
          "- Opened **12** pull requests\n- Reviewed **34** pull requests\n- Merged **8** commits",
        button_url: "https://github.com/boostorg",
        button_label: "View on GitHub",
      },
      poll_exhausted: false,
    }}
  />
);

export const Refreshing = () => (
  <Pattern
    template="v3/includes/_github_activity_card.html"
    context={{
      data: {
        refreshing: true,
        title: "Recent GitHub Activity",
        markdown_text:
          "- Opened **12** pull requests\n- Reviewed **34** pull requests\n- Merged **8** commits",
        button_url: "https://github.com/boostorg",
        button_label: "View on GitHub",
      },
      poll_exhausted: false,
      poll_url: "#",
      poll_interval: 9999,
    }}
  />
);
