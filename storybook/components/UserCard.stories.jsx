import React from "react";
import {Pattern} from "storybook-django/src/react";

export default {
  title: "Components/User Card",
};

export const Full = (args) => (
  <Pattern
    template="v3/includes/_user_card.html"
    context={args}
  />
);
Full.storyName = "Full (card variant)";
Full.args = {
  username: "vinniefalco",
  avatar_url: "https://avatars.githubusercontent.com/u/1503976",
  badge_name: "Bug Catcher",
  badge_icon_src: "",
  member_since: "2008",
  role: "C++ Alliance Board Member",
  flag_emoji: "🇺🇸",
  cta_url: "#",
  cta_label: "Create Post",
}

export const Compact = (args) => (
  <Pattern
    template="v3/includes/_user_card.html"
    context={args}
  />
);
Compact.storyName = "Compact (no background, no CTA)";
Compact.args = {
  username: "vinniefalco",
  avatar_url: "https://avatars.githubusercontent.com/u/1503976",
  badge_name: "Bug Catcher",
  member_since: "2008",
  role: "C++ Alliance Board Member",
  compact: true,
}

export const Minimal = (args) => (
  <Pattern
    template="v3/includes/_user_card.html"
    context={args}
  />
);
Minimal.storyName = "Minimal (username only)";
Minimal.args = {
  username: "contributor42",
  cta_url: "#",
}
