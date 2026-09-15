import React from "react";
import { Pattern } from "storybook-django/src/react";
import { DEMO_AUTHORS } from "../mockData";

export default {
  title: "Components/Post List Card",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_post_list_card.html"
    context={{
      heading: "Posts",
      items: [
        {
          title: "A talk by Richard Thomson at the Utah C++ Programmers Group",
          get_absolute_url: "#",
          created_at: "2025-03-03T10:00:00Z",
          type_label: "Video",
          tag: "beast",
          author: DEMO_AUTHORS[3],
        },
        {
          title: "Boost.Bind and modern C++: a quick overview",
          get_absolute_url: "#",
          created_at: "2025-02-15T10:00:00Z",
          type_label: "Blog",
          tag: "bind",
          author: DEMO_AUTHORS[4],
        },
        {
          title: "C++ Alliance announces new Boost.JSON improvements",
          get_absolute_url: "#",
          created_at: "2025-01-20T10:00:00Z",
          type_label: "News",
          tag: "json",
          author: DEMO_AUTHORS[1],
        },
      ],
    }}
  />
);

export const Empty = () => (
  <Pattern
    template="v3/includes/_post_list_card.html"
    context={{ heading: "Posts", items: [] }}
  />
);
