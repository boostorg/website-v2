import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Post Card",
  argTypes: {
    post_title: { control: "text" },
    post_url: { control: "text" },
    post_date: { control: "text" },
    post_category: { control: "text" },
    post_tag: { control: "text" },
    author_name: { control: "text" },
    author_role: { control: "text" },
    author_avatar_url: { control: "text" },
    author_show_badge: { control: "boolean" },
  },
};

export const Default = (args) => (
  <Pattern template="v3/includes/_post_card_v3.html" context={args} />
);
Default.args = {
  post_title:
    "A talk by Richard Thomson at the Utah C++ Programmers Group",
  post_url: "#",
  post_date: "03/03/2025",
  post_category: "Issues",
  post_tag: "beast",
  author_name: "Richard Thomson",
  author_role: "Contributor",
  author_avatar_url:
    "https://ui-avatars.com/api/?name=Richard+Thomson&size=48",
  author_show_badge: true,
};

export const WithoutBadge = Default.bind({});
WithoutBadge.args = {
  post_title: "Boost.Bind and modern C++: a quick overview",
  post_url: "#",
  post_date: "15/02/2025",
  post_category: "Releases",
  post_tag: "bind",
  author_name: "Alex Morgan",
  author_role: "Contributor",
  author_avatar_url: "https://thispersondoesnotexist.com/",
  author_show_badge: false,
};
