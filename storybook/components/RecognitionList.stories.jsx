import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Recognition List",
};

export const Achievements = () => (
  <Pattern
    template="v3/includes/_recognition_list.html"
    context={{
      list_label: "Achievements",
      items: [
        {
          token: "achievement-count",
          count: 12,
          name: "First Contribution",
          description: "Made your first accepted contribution to a Boost library.",
        },
        {
          token: "achievement-count",
          count: 3,
          name: "Review Streak",
          description: "Reviewed pull requests three release cycles in a row.",
        },
        {
          token: "boost-day",
          name: "Boost Day",
          description: "Participated in an official Boost Day event.",
        },
      ],
    }}
  />
);

export const Badges = () => (
  <Pattern
    template="v3/includes/_recognition_list.html"
    context={{
      list_label: "Badge types",
      items: [
        {
          token: "badge-tier-1",
          name: "Patch Wizard",
          description: "Bronze tier: land your first accepted patch.",
        },
        {
          token: "badge-tier-3",
          name: "Review Hawk",
          description: "Gold tier: complete 50 code reviews.",
        },
        {
          token: "star-tier-1",
          name: "Library Alchemist",
          description: "Maintain a library for at least a year.",
        },
      ],
    }}
  />
);
