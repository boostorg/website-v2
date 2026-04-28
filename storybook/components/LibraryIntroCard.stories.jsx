import React from "react";
import { Pattern } from "storybook-django/src/react";

const sampleAuthors = [
  {
    name: "Vinnie Falco",
    profile_url: "#",
    role: "Author & Maintainer",
    avatar_url: "https://picsum.photos/seed/vinnie/80/80",
    bio: "Creator of Beast and other Boost libraries.",
  },
  {
    name: "Chris Kohlhoff",
    profile_url: "#",
    role: "Contributor",
    avatar_url: "https://picsum.photos/seed/chris/80/80",
  },
];

export default {
  title: "Components/Library Intro Card",
};

export const WithAuthors = () => (
  <Pattern
    template="v3/includes/_library_intro_card.html"
    context={{
      library_name: "Boost.Beast",
      description: "HTTP and WebSocket built on Boost.Asio in C++11.",
      authors: sampleAuthors,
      cta_url: "/libs/beast/",
    }}
  />
);
WithAuthors.storyName = "With Authors";

export const SingleAuthor = () => (
  <Pattern
    template="v3/includes/_library_intro_card.html"
    context={{
      library_name: "Boost.Core",
      description: "Lightweight utilities that power dozens of other Boost libraries.",
      authors: [sampleAuthors[0]],
      cta_url: "/libs/core/",
      cta_label: "Use Boost.Core",
    }}
  />
);
SingleAuthor.storyName = "Single Author";

export const NoAuthors = () => (
  <Pattern
    template="v3/includes/_library_intro_card.html"
    context={{
      library_name: "Boost.Filesystem",
      description: "Library providing portable facilities to query and manipulate paths, files, and directories.",
      authors: [],
      cta_url: "/libs/filesystem/",
    }}
  />
);
NoAuthors.storyName = "No Authors";

export const NoCTA = () => (
  <Pattern
    template="v3/includes/_library_intro_card.html"
    context={{
      library_name: "Boost.Spirit",
      description: "A set of C++ libraries for parsing and output generation.",
      authors: [sampleAuthors[0]],
    }}
  />
);
NoCTA.storyName = "No CTA";
