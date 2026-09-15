import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Badges Modal",
};

const DEMO_ITEMS = [
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
];

export const Default = () => (
  <div>
    <button
      className="btn btn-primary"
      onClick={(e) => {
        e.preventDefault();
        window.location.hash = "badges-modal";
      }}
    >
      Open dialog
    </button>
    <Pattern
      template="v3/includes/_badges_modal.html"
      context={{ items: DEMO_ITEMS }}
    />
  </div>
);
