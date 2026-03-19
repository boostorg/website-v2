import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/User Profile",
};

export const WithBio = () => (
  <Pattern
    template="v3/includes/_user_profile.html"
    context={{
      author: {
        name: "Vinnie Falco",
        profile_url: "#",
        role: "Author & Maintainer",
        avatar_url: "https://picsum.photos/seed/vinnie/80/80",
        bio: "Creator of Boost.Beast and Boost.JSON. C++ Alliance board member.",
      },
    }}
  />
);
WithBio.storyName = "With Bio";

export const NoBio = () => (
  <Pattern
    template="v3/includes/_user_profile.html"
    context={{
      author: {
        name: "Chris Kohlhoff",
        profile_url: "#",
        role: "Contributor",
        avatar_url: "https://picsum.photos/seed/chris/80/80",
      },
    }}
  />
);
NoBio.storyName = "No Bio";

export const WithBadge = () => (
  <Pattern
    template="v3/includes/_user_profile.html"
    context={{
      author: {
        name: "Peter Dimov",
        profile_url: "#",
        role: "Maintainer",
        avatar_url: "https://picsum.photos/seed/peter/80/80",
        badge_url: "/static/img/icons/badge-star.svg",
        bio: "Maintainer of several core Boost libraries.",
      },
    }}
  />
);
WithBadge.storyName = "With Badge Icon";

export const NoProfileLink = () => (
  <Pattern
    template="v3/includes/_user_profile.html"
    context={{
      author: {
        name: "Anonymous Contributor",
        role: "Contributor",
        avatar_url: "",
      },
    }}
  />
);
NoProfileLink.storyName = "No Profile Link";
