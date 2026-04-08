import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Why Boost Cards",
};

const CARDS_DATA = [
  {
    title: "Get help",
    description: "Tap into quick answers, networking, and chat with 24,000+ members.",
    icon_name: "bullseye-arrow",
  },
  {
    title: "Documentation",
    description: "Browse library docs, examples, and release notes in one place.",
    icon_name: "link",
  },
  {
    title: "Community",
    description: "Mailing lists, GitHub, and community guidelines for contributors.",
    icon_name: "human",
  },
  {
    title: "Releases",
    description: "Latest releases, download links, and release notes.",
    icon_name: "info-box",
  },
  {
    title: "Learn",
    description: "Access documentation, books, and courses to level up your C++.",
    icon_name: "bullseye-arrow",
  },
  {
    title: "Contribute",
    description: "Report issues, submit patches, and join the community.",
    icon_name: "bullseye-arrow",
  },
  {
    title: "Stay updated",
    description: "Releases, news, and announcements from the Boost community.",
    icon_name: "bullseye-arrow",
  },
  {
    title: "Libraries",
    description: "Portable, peer-reviewed libraries for a wide range of use cases.",
    icon_name: "bullseye-arrow",
  },
  {
    title: "Standards",
    description: "Many Boost libraries have been adopted into the C++ standard.",
    icon_name: "bullseye-arrow",
  },
  {
    title: "Quality",
    description: "Peer-reviewed code and documentation maintained by the community.",
    icon_name: "bullseye-arrow",
  },
  {
    title: "Cross-platform",
    description: "Libraries designed to work across compilers and platforms.",
    icon_name: "bullseye-arrow",
  },
];

export const Grid = () => (
  <Pattern
    template="v3/includes/_why_boost_cards.html"
    context={{ why_boost_cards: CARDS_DATA }}
  />
);
