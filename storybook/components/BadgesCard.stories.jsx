import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Badges Card",
};

const BADGE_ICON_SRCS = [
  "/static/img/v3/badges/badge-first-place.png",
  "/static/img/v3/badges/badge-second-place.png",
  "/static/img/v3/badges/badge-bronze.png",
  "/static/img/v3/badges/badge-gold-medal.png",
  "/static/img/v3/badges/badge-military-star.png",
];

const DEMO_BADGES = [
  {
    icon_src: "/static/img/v3/badges/badge-first-place.png",
    name: "Patch Wizard",
    earned_date: "08/08/2025",
  },
  {
    icon_src: "/static/img/v3/badges/badge-gold-medal.png",
    name: "Standard Bearer",
    earned_date: "03/07/2025",
  },
  {
    icon_src: "/static/img/v3/badges/badge-military-star.png",
    name: "Review Hawk",
    earned_date: "03/06/2025",
  },
  {
    icon_src: "/static/img/v3/badges/badge-second-place.png",
    name: "Library Alchemist",
    earned_date: "03/04/2025",
  },
  {
    icon_src: "/static/img/v3/badges/badge-first-place.png",
    name: "Bug Catcher",
    earned_date: "02/04/2025",
  },
  {
    icon_src: "/static/img/v3/badges/badge-bronze.png",
    name: "Code Whisperer",
    earned_date: "01/01/2025",
  },
];

export const EmptyWithCTA = () => (
  <Pattern
    template="v3/includes/_badges_card.html"
    context={{
      cta_url: "#",
      cta_label: "Explore available badges and how to earn them",
      empty_icon_srcs: BADGE_ICON_SRCS,
    }}
  />
);

export const EmptyWithoutCTA = () => (
  <Pattern
    template="v3/includes/_badges_card.html"
    context={{
      empty_icon_srcs: BADGE_ICON_SRCS,
    }}
  />
);

export const FilledSixBadges = () => (
  <Pattern
    template="v3/includes/_badges_card.html"
    context={{
      badges: DEMO_BADGES,
    }}
  />
);
FilledSixBadges.storyName = "Filled (6 badges)";

export const FilledTwoBadges = () => (
  <Pattern
    template="v3/includes/_badges_card.html"
    context={{
      badges: DEMO_BADGES.slice(0, 2),
    }}
  />
);
FilledTwoBadges.storyName = "Filled (2 badges)";
