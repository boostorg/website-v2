import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Create Account Card",
  argTypes: {
    heading: { control: "text" },
    cta_url: { control: "text" },
    cta_label: { control: "text" },
    preview_image_url: { control: "text" },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_create_account_card.html"
    context={{
      heading: args.heading,
      body_html:
        "<p>Your contribution badges appear on your Boost profile with:</p><ul><li>Contribution statistics</li><li>Progress towards next badge</li><li>Recent activity feed</li></ul>",
      preview_image_url: args.preview_image_url,
      cta_url: args.cta_url,
      cta_label: args.cta_label,
    }}
  />
);
Default.args = {
  heading:
    "Contribute to earn badges, track your progress and grow your impact",
  preview_image_url: "/static/img/checker.png",
  cta_url: "#",
  cta_label: "Start contributing",
};
