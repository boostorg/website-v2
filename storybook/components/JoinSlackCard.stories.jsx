import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Join Slack Card",
  argTypes: {
    slack_member_count: { control: "text" },
  },
};

export const Default = (args) => (
  <Pattern template="v3/includes/_join_slack_card.html" context={args} />
);
Default.args = {
  slack_member_count: "24,000+",
};
