import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Cards Carousel",
};

const DEMO_CARDS = [
  {
    title: "Get help",
    description:
      "Tap into quick answers, networking, and chat with 24,000+ members.",
    icon_name: "info-box",
    cta_label: "Start here",
    cta_href: "#",
  },
  {
    title: "Documentation",
    description:
      "Browse library docs, examples, and release notes in one place.",
    icon_name: "link",
    cta_label: "View docs",
    cta_href: "#",
  },
  {
    title: "Community",
    description:
      "Mailing lists, GitHub, and community guidelines for contributors.",
    icon_name: "human",
    cta_label: "Join",
    cta_href: "#",
  },
  {
    title: "Releases",
    description: "Latest releases, download links, and release notes.",
    icon_name: "info-box",
    cta_label: "Download",
    cta_href: "#",
  },
  {
    title: "Libraries",
    description:
      "Explore the full catalog of Boost C++ libraries with docs and metadata.",
    icon_name: "link",
    cta_label: "Browse libraries",
    cta_href: "#",
  },
  {
    title: "News",
    description:
      "Blog posts, announcements, and community news from the Boost project.",
    icon_name: "device-tv",
    cta_label: "Read news",
    cta_href: "#",
  },
  {
    title: "Getting started",
    description:
      "Step-by-step guides to build and use Boost in your projects.",
    icon_name: "bullseye-arrow",
    cta_label: "Get started",
    cta_href: "#",
  },
  {
    title: "Resources",
    description:
      "Learning resources, books, and other materials for Boost users.",
    icon_name: "get-help",
    cta_label: "View resources",
    cta_href: "#",
  },
  {
    title: "Calendar",
    description: "Community events, meetings, and review schedule.",
    icon_name: "info-box",
    cta_label: "View calendar",
    cta_href: "#",
  },
  {
    title: "Donate",
    description:
      "Support the Boost Software Foundation and open-source C++.",
    icon_name: "human",
    cta_label: "Donate",
    cta_href: "#",
  },
];

export const Default = () => (
  <Pattern
    template="v3/includes/_cards_carousel_v3.html"
    context={{
      carousel_id: "post-cards-carousel-demo",
      heading: "Libraries categories",
      cards: DEMO_CARDS,
    }}
  />
);

export const WithAutoplay = () => (
  <Pattern
    template="v3/includes/_cards_carousel_v3.html"
    context={{
      carousel_id: "post-cards-carousel-demo-autoplay",
      heading: "Libraries categories",
      cards: DEMO_CARDS,
      autoplay: true,
      autoplay_delay: 5000,
    }}
  />
);

export const WithInfiniteAndAutoplay = () => (
  <Pattern
    template="v3/includes/_cards_carousel_v3.html"
    context={{
      carousel_id: "post-cards-carousel-demo-infinite-autoplay",
      heading: "Libraries categories",
      cards: DEMO_CARDS,
      infinite: true,
      autoplay: true,
      autoplay_delay: 5000,
    }}
  />
);
WithInfiniteAndAutoplay.storyName = "Infinite Loop + Autoplay";
