import React from "react";
import { Pattern } from "storybook-django/src/react";
import { DEMO_AUTHORS } from "../mockData";

export default {
  title: "Components/Help Card",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_help_card.html"
    context={{
      heading: "What do you need help with?",
      items: [
        {
          quote: "How do I get started with Boost?",
          description: "Check out our getting started guide for a walkthrough of installing and using Boost libraries.",
          author: DEMO_AUTHORS[0],
          cta_text: "Read the guide",
          cta_url: "#",
        },
        {
          quote: "I found a bug, what now?",
          description: "Report issues on GitHub so maintainers can triage and fix them.",
          author: DEMO_AUTHORS[1],
          cta_text: "Report a bug",
          cta_url: "#",
        },
        {
          quote: "How can I contribute?",
          description: "Join the community and start contributing to libraries you use.",
          author: DEMO_AUTHORS[2],
          cta_text: "See contribution guide",
          cta_url: "#",
        },
      ],
    }}
  />
);
