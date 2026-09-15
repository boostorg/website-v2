import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Badge Button Group",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_badge_button_group.html"
    context={{
      group_label: "Select a badge to display",
      group_name: "display-badge-demo",
      badge_buttons: [
        { value: "bronze", icon: "badge-tier-1", icon_alt: "Bronze badge" },
        { value: "silver", icon: "badge-tier-2", icon_alt: "Silver badge" },
        {
          value: "gold",
          icon: "badge-tier-3",
          icon_alt: "Gold badge",
          checked: true,
        },
        { value: "boost-day", icon: "boost-day", icon_alt: "Boost Day" },
      ],
    }}
  />
);
