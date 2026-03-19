import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Avatar",
  argTypes: {
    src: { control: "text", description: "Image URL" },
    name: { control: "text", description: "Name (for initials)" },
    variant: {
      control: "select",
      options: ["yellow", "green", "teal"],
      description: "Color variant for initials avatar",
    },
    size: {
      control: "select",
      options: ["sm", "md", "lg", "xl"],
      description: "Avatar size",
    },
  },
};

export const WithImage = (args) => (
  <Pattern
    template="v3/includes/_avatar_v3.html"
    context={{
      src: args.src,
      size: args.size,
    }}
  />
);
WithImage.args = {
  src: "https://thispersondoesnotexist.com/",
  size: "md",
};

export const WithInitials = (args) => (
  <Pattern
    template="v3/includes/_avatar_v3.html"
    context={{
      name: args.name,
      variant: args.variant,
      size: args.size,
    }}
  />
);
WithInitials.args = {
  name: "Jane Doe",
  variant: "yellow",
  size: "md",
};

export const YellowVariant = WithInitials.bind({});
YellowVariant.args = { name: "Jane Doe", variant: "yellow", size: "md" };

export const GreenVariant = WithInitials.bind({});
GreenVariant.args = { name: "Jane Doe", variant: "green", size: "md" };

export const TealVariant = WithInitials.bind({});
TealVariant.args = { name: "Jane Doe", variant: "teal", size: "md" };

export const Placeholder = () => (
  <Pattern template="v3/includes/_avatar_v3.html" context={{}} />
);

export const SizeSmall = WithInitials.bind({});
SizeSmall.args = { name: "JD", variant: "yellow", size: "sm" };
SizeSmall.storyName = "Size: Small";

export const SizeMedium = WithInitials.bind({});
SizeMedium.args = { name: "JD", variant: "yellow", size: "md" };
SizeMedium.storyName = "Size: Medium";

export const SizeLarge = WithInitials.bind({});
SizeLarge.args = { name: "JD", variant: "yellow", size: "lg" };
SizeLarge.storyName = "Size: Large";

export const SizeExtraLarge = WithInitials.bind({});
SizeExtraLarge.args = { name: "JD", variant: "yellow", size: "xl" };
SizeExtraLarge.storyName = "Size: Extra Large";
