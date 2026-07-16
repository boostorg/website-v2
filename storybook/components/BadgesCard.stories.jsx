import React from "react";
import { Pattern } from "storybook-django/src/react";
import { DEMO_BADGES } from "../mockData";

export default {
  title: "Components/Badges Card",
};

export const EmptyWithCTA = () => (
  <Pattern
    template="v3/includes/_badges_card.html"
    context={{
      cta_url: "#",
      cta_label: "Explore available badges and how to earn them",
    }}
  />
);

export const EmptyWithoutCTA = () => (
  <Pattern template="v3/includes/_badges_card.html" context={{}} />
);

export const FilledSixBadges = () => (
  <Pattern
    template="v3/includes/_badges_card.html"
    context={{ badges: DEMO_BADGES }}
  />
);
FilledSixBadges.storyName = "Filled (6 badges)";

export const FilledTwoBadges = () => (
  <Pattern
    template="v3/includes/_badges_card.html"
    context={{ badges: DEMO_BADGES.slice(0, 2) }}
  />
);
FilledTwoBadges.storyName = "Filled (2 badges)";
