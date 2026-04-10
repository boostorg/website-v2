import React from "react";
import { Pattern } from "storybook-django/src/react";

const sampleSets = [
  {
    title: "JSON parse (MB/s)",
    rows: [
      { label: "Boost.JSON", value: "890 MB/s", width_pct: 100 },
      { label: "RapidJSON", value: "780 MB/s", width_pct: 88 },
      { label: "nlohmann/json", value: "340 MB/s", width_pct: 38 },
      { label: "simdjson", value: "850 MB/s", width_pct: 96 },
    ],
  },
  {
    title: "JSON serialize (MB/s)",
    rows: [
      { label: "Boost.JSON", value: "1200 MB/s", width_pct: 100 },
      { label: "RapidJSON", value: "990 MB/s", width_pct: 83 },
      { label: "nlohmann/json", value: "510 MB/s", width_pct: 43 },
      { label: "simdjson", value: "640 MB/s", width_pct: 53 },
    ],
  },
];

export default {
  title: "Components/Stats Benchmarks",
  argTypes: {
    theme: {
      control: "select",
      options: ["default", "yellow", "green", "teal"],
    },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_stats_benchmarks.html"
    context={args}
  />
);
Default.args = {
  heading: "Performance benchmarks",
  sets: sampleSets,
  theme: "default",
};

export const Yellow = (args) => (
  <Pattern
    template="v3/includes/_stats_benchmarks.html"
    context={args}
  />
);
Yellow.args = {
  heading: "Performance benchmarks",
  sets: sampleSets,
  theme: "yellow",
};

export const Green = (args) => (
  <Pattern
    template="v3/includes/_stats_benchmarks.html"
    context={args}
  />
);
Green.args = {
  heading: "Performance benchmarks",
  sets: sampleSets,
  theme: "green",
};

export const Teal = (args) => (
  <Pattern
    template="v3/includes/_stats_benchmarks.html"
    context={args}
  />
);
Teal.args = {
  heading: "Performance benchmarks",
  sets: sampleSets,
  theme: "teal",
};
