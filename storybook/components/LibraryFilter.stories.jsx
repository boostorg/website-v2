import React from "react";
import { Pattern } from "storybook-django/src/react";

const dropdownFields = [
  {
    type: "dropdown",
    name: "boost_version",
    label: "Boost Version",
    options: [
      ["1.88.0", "Boost 1.88.0"],
      ["1.87.0", "Boost 1.87.0"],
      ["1.86.0", "Boost 1.86.0"],
    ],
    selected: "1.88.0",
  },
  {
    type: "dropdown",
    name: "cpp_standard",
    label: "C++ Standard",
    options: [
      ["cpp03", "C++03"],
      ["cpp11", "C++11"],
      ["cpp14", "C++14"],
      ["cpp17", "C++17"],
      ["cpp20", "C++20"],
    ],
    selected: "",
    placeholder: "Any standard",
  },
  {
    type: "combo_multi",
    name: "category",
    label: "Category",
    options: [
      ["algorithms", "Algorithms"],
      ["containers", "Containers"],
      ["io", "I/O"],
      ["math", "Math & Numerics"],
      ["networking", "Networking"],
      ["string", "String & Text"],
    ],
    selected_values: [],
    placeholder: "All categories",
    width: "wide",
  },
];

export default {
  title: "Components/Library Filter",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_library_filter.html"
    context={{ filter_id: "library-filter-demo", fields: dropdownFields }}
  />
);

export const WithSelection = () => (
  <Pattern
    template="v3/includes/_library_filter.html"
    context={{
      filter_id: "library-filter-selected",
      fields: [
        { ...dropdownFields[0], selected: "1.87.0" },
        { ...dropdownFields[1], selected: "cpp17" },
        { ...dropdownFields[2], selected_values: ["algorithms", "math"] },
      ],
    }}
  />
);
WithSelection.storyName = "With Pre-selected Values";
