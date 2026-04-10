import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/User Profile",
};

export const WithBio = (args) => (
  <Pattern
    template="v3/includes/_user_profile.html"
    context={{ author: args }}
  />
);
WithBio.storyName = "With Bio";
WithBio.args = {
  name: "Vinnie Falco",
  profile_url: "#",
  role: "Author & Maintainer",
  avatar_url: "https://avatars.githubusercontent.com/u/1503976",
  bio: "Creator of Boost.Beast and Boost.JSON. C++ Alliance board member.",
};

export const NoBio = (args) => (
  <Pattern
    template="v3/includes/_user_profile.html"
    context={{ author: args }}
  />
);
NoBio.storyName = "No Bio";
NoBio.args = {
  name: "Chris Kohlhoff",
  profile_url: "#",
  role: "Contributor",
  avatar_url: "https://picsum.photos/seed/chris/80/80",
};

export const WithBadge = (args) => (
  <Pattern
    template="v3/includes/_user_profile.html"
    context={{ author: args }}
  />
);
WithBadge.storyName = "With Badge Icon";
WithBadge.args = {
  name: "Peter Dimov",
  profile_url: "#",
  role: "Maintainer",
  avatar_url: "https://picsum.photos/seed/peter/80/80",
  badge_url: "/static/img/icons/badge-star.svg",
  bio: "Maintainer of several core Boost libraries.",
};

export const NoProfileLink = (args) => (
  <Pattern
    template="v3/includes/_user_profile.html"
    context={{ author: args }}
  />
);
NoProfileLink.storyName = "No Profile Link";
NoProfileLink.args = {
  name: "Anonymous Contributor",
  role: "Contributor",
  avatar_url: "",
};
