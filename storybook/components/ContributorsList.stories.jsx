import React from "react";
import { Pattern } from "storybook-django/src/react";
import { DEMO_AUTHORS } from "../mockData";

export default {
  title: "Components/Contributors List",
};

export const Release = () => (
  <Pattern
    template="v3/includes/_contributors_list.html"
    context={{
      title: "Contributors: This Release",
      variant: "release",
      contributors: DEMO_AUTHORS.slice(0, 4),
    }}
  />
);
Release.storyName = "Release contributors";

export const All = () => (
  <Pattern
    template="v3/includes/_contributors_list.html"
    context={{
      title: "All Contributors",
      variant: "all",
      contributors: DEMO_AUTHORS,
    }}
  />
);
All.storyName = "All contributors";

export const SingleContributor = () => (
  <Pattern
    template="v3/includes/_contributors_list.html"
    context={{
      title: "Contributors: This Release",
      variant: "release",
      contributors: [DEMO_AUTHORS[0]],
    }}
  />
);
SingleContributor.storyName = "Single contributor";
