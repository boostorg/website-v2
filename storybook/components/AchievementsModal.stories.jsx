import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Achievements Modal",
};

const DEMO_ITEMS = [
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
];

export const Default = () => (
  <div>
    <button
      className="btn btn-primary"
      onClick={(e) => {
        e.preventDefault();
        window.location.hash = "achievements-modal";
      }}
    >
      Open dialog
    </button>
    <Pattern
      template="v3/includes/_achievements_modal.html"
      context={{ items: DEMO_ITEMS }}
    />
  </div>
);
