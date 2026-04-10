import React from "react";
import { Pattern } from "storybook-django/src/react";

const sampleBars = [
  { label: "1.70.0", height_px: 32 },
  { label: "1.71.0", height_px: 48 },
  { label: "1.72.0", height_px: 55 },
  { label: "1.73.0", height_px: 41 },
  { label: "1.74.0", height_px: 63 },
  { label: "1.75.0", height_px: 78 },
  { label: "1.76.0", height_px: 52 },
  { label: "1.77.0", height_px: 90 },
  { label: "1.78.0", height_px: 67 },
  { label: "1.79.0", height_px: 85 },
];

export default {
  title: "Components/Stats In Numbers",
  argTypes: {
    theme: {
      control: "select",
      options: ["default", "yellow", "green", "teal"],
    },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_stats_in_numbers.html"
    context={args}
  />
);
Default.args = {
  heading: "Commits per release",
  description: "Commit count by Boost release for this library.",
  theme: "default",
  primary_cta_label: "View library",
  primary_cta_url: "#",
  bars: sampleBars
};

export const Yellow = (args) => (
  <Pattern
    template="v3/includes/_stats_in_numbers.html"
    context={args}
  />
);
Yellow.args = {
  heading: "Commits per release",
  description: "Commit count by Boost release for this library.",
  theme: "yellow",
  primary_cta_label: "View library",
  primary_cta_url: "#",
  bars: sampleBars
};

export const Green = (args) => (
  <Pattern
    template="v3/includes/_stats_in_numbers.html"
    context={args}
  />
);
Green.args = {
  heading: "Commits per release",
  description: "Commit count by Boost release for this library.",
  theme: "green",
  primary_cta_label: "View library",
  primary_cta_url: "#",
  secondary_cta_label: "View all libraries",
  secondary_cta_url: "#",
  bars: sampleBars
};

export const Teal = (args) => (
  <Pattern
    template="v3/includes/_stats_in_numbers.html"
    context={args}
  />
);
Teal.args = {
  heading: "Commits per release",
  description: "Commit count by Boost release for this library.",
  theme: "teal",
  primary_cta_label: "View library",
  primary_cta_url: "#",
  bars: sampleBars
};
