import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/User Card",
};

export const Full = () => (
  <Pattern
    template="v3/includes/_user_card.html"
    context={{
      username: "vinniefalco",
      avatar_url: "https://picsum.photos/seed/vinnie/80/80",
      badge_name: "Bug Catcher",
      badge_icon_src: "",
      member_since: "2008",
      role: "C++ Alliance Board Member",
      flag_emoji: "🇺🇸",
      cta_url: "#",
      cta_label: "Create Post",
    }}
  />
);
Full.storyName = "Full (card variant)";

export const Compact = () => (
  <Pattern
    template="v3/includes/_user_card.html"
    context={{
      username: "vinniefalco",
      avatar_url: "https://picsum.photos/seed/vinnie/80/80",
      badge_name: "Bug Catcher",
      member_since: "2008",
      role: "C++ Alliance Board Member",
      compact: true,
    }}
  />
);
Compact.storyName = "Compact (no background, no CTA)";

export const Minimal = () => (
  <Pattern
    template="v3/includes/_user_card.html"
    context={{
      username: "contributor42",
      cta_url: "#",
    }}
  />
);
Minimal.storyName = "Minimal (username only)";
