import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Category Tag",
  argTypes: {
    tag_label: { control: "text" },
    variant: {
      control: "select",
      options: ["neutral", "green", "yellow", "teal"],
    },
    size: { control: "select", options: ["default", "tight"] },
    url: { control: "text" },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_category_tag.html"
    context={{
      tag_label: args.tag_label,
      variant: args.variant,
      size: args.size,
      url: args.url,
    }}
  />
);
Default.args = {
  tag_label: "Networking",
  variant: "neutral",
  size: "default",
  url: "#",
};

export const NonClickable = () => (
  <Pattern
    template="v3/includes/_category_tag.html"
    context={{ tag_label: "Math", variant: "neutral" }}
  />
);
NonClickable.storyName = "Non-clickable (no URL)";

export const AllVariants = () => (
  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
    {["neutral", "green", "yellow", "teal"].map((variant) => (
      <Pattern
        key={variant}
        template="v3/includes/_category_tag.html"
        context={{ tag_label: variant, variant, url: "#" }}
      />
    ))}
  </div>
);
AllVariants.storyName = "All Colour Variants";

export const Tight = () => (
  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
    {["neutral", "green", "yellow", "teal"].map((variant) => (
      <Pattern
        key={variant}
        template="v3/includes/_category_tag.html"
        context={{ tag_label: variant, variant, size: "tight", url: "#" }}
      />
    ))}
  </div>
);
Tight.storyName = "Tight size";
