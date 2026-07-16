import React from "react";
import { Pattern } from "storybook-django/src/react";

const ALL_BADGE_TOKENS = [
  "badge-tier-1",
  "badge-tier-2",
  "badge-tier-3",
  "badge-tier-4",
  "badge-tier-5",
  "star-tier-1",
  "star-tier-2",
  "star-tier-3",
  "star-tier-4",
  "star-tier-5",
  "boost-day",
  "achievement-count",
];

export default {
  title: "Components/Badge",
  argTypes: {
    token: { control: "select", options: ALL_BADGE_TOKENS },
    size: { control: "select", options: ["small", "medium", "large"] },
    label: { control: "text" },
    count: {
      control: "number",
      description: "Only used when token is achievement-count.",
    },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_badge_v3.html"
    context={{ token: args.token, label: args.label, size: args.size }}
  />
);
Default.args = { token: "badge-tier-3", label: "Gold Badge", size: "medium" };

export const AchievementCount = (args) => (
  <Pattern
    template="v3/includes/_badge_v3.html"
    context={{ token: "achievement-count", count: args.count, size: args.size }}
  />
);
AchievementCount.storyName = "Achievement Count";
AchievementCount.args = { count: 5, size: "medium" };
AchievementCount.argTypes = {
  token: { table: { disable: true } },
  label: { table: { disable: true } },
};

export const AchievementCountLarge = () => (
  <Pattern
    template="v3/includes/_badge_v3.html"
    context={{ token: "achievement-count", count: 2347, size: "medium" }}
  />
);
AchievementCountLarge.storyName = "Achievement Count (compact, 2347)";

export const TierBadges = () => (
  <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
    {["badge-tier-1", "badge-tier-2", "badge-tier-3", "badge-tier-4", "badge-tier-5"].map(
      (token) => (
        <Pattern
          key={token}
          template="v3/includes/_badge_v3.html"
          context={{ token, size: "large" }}
        />
      )
    )}
  </div>
);
TierBadges.storyName = "All Tier Badges (1-5)";

export const StarTiers = () => (
  <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
    {["star-tier-1", "star-tier-2", "star-tier-3", "star-tier-4", "star-tier-5"].map(
      (token) => (
        <Pattern
          key={token}
          template="v3/includes/_badge_v3.html"
          context={{ token, size: "large" }}
        />
      )
    )}
  </div>
);
StarTiers.storyName = "All Star Tiers (1-5)";

export const BoostDay = () => (
  <Pattern
    template="v3/includes/_badge_v3.html"
    context={{ token: "boost-day", size: "large" }}
  />
);
BoostDay.storyName = "Boost Day";

export const Sizes = () => (
  <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
    {["small", "medium", "large"].map((size) => (
      <Pattern
        key={size}
        template="v3/includes/_badge_v3.html"
        context={{ token: "badge-tier-3", size, label: size }}
      />
    ))}
  </div>
);
Sizes.storyName = "Size Comparison (small / medium / large)";
