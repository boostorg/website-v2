import React from "react";
import { Pattern } from "storybook-django/src/react";
import { DEMO_AUTHOR } from "../mockData";

export default {
  title: "Components/Post Header",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_post_header.html"
    context={{
      title: "C++ Alliance announces new Boost.JSON improvements",
      publish_date: "2025-01-20T09:00:00Z",
      tag: "json",
      author: DEMO_AUTHOR,
    }}
  />
);

export const NoAuthor = () => (
  <Pattern
    template="v3/includes/_post_header.html"
    context={{
      title: "Boost 1.90.0 closed for major changes",
      publish_date: "2025-10-29T09:00:00Z",
    }}
  />
);
NoAuthor.storyName = "No Author";
