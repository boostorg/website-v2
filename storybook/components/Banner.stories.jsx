import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Banner",
  argTypes: {
    icon_name: { control: "text", description: "Icon name" },
    banner_message: { control: "text", description: "Banner HTML message" },
    fade_time: {
      control: "number",
      description: "Auto-fade delay in ms (0 = no fade)",
    },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_banner.html"
    context={{
      icon_name: args.icon_name,
      banner_message: args.banner_message,
    }}
  />
);
Default.args = {
  icon_name: "alert",
  banner_message:
    "This is an older version of Boost and was released in 2017. The <a href='https://www.example.com'>current version</a> is 1.90.0.",
};

export const WithFade = (args) => (
  <Pattern
    template="v3/includes/_banner.html"
    context={{
      icon_name: args.icon_name,
      banner_message: args.banner_message,
      fade_time: args.fade_time,
    }}
  />
);
WithFade.args = {
  icon_name: "alert",
  banner_message:
    "This is an older version of Boost and was released in 2017. The <a href='https://www.example.com'>current version</a> is 1.90.0.",
  fade_time: 5000,
};
