import React from "react";
import { Pattern } from "storybook-django/src/react";

// NOTE: show_branch_buttons is deliberately never set on these stories. When
// true, _hero_library.html includes _branch_buttons.html, which calls
// {% branch_url_tag request.resolver_match.view_name ... %} - inside
// Storybook's pattern-library render, resolver_match points at the
// pattern-library API view itself, so reverse() raises NoReverseMatch. This
// is the same blocker documented on the (also story-less) _branch_buttons.html
// component; it needs real page routing to render, which a standalone
// pattern-library render can't fake. See the PR's open items.

export default {
  title: "Components/Hero Library",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_hero_library.html"
    context={{
      title: "Boost.Beast",
      description:
        "Portable HTTP, WebSocket, and network operations using only C++11 and Boost.Asio",
      doc_url: "#",
      source_url: "#",
      slack_url: "#",
      github_url: "#",
      version_tag: "C++ 03",
      first_boost_version: "1.66.0",
      hero_image_url: "https://picsum.photos/seed/hero-library/480/320",
      is_flagship_lib: true,
    }}
  />
);

export const NoImage = () => (
  <Pattern
    template="v3/includes/_hero_library.html"
    context={{
      title: "Boost.Beast",
      description:
        "Portable HTTP, WebSocket, and network operations using only C++11 and Boost.Asio",
      doc_url: "#",
      source_url: "#",
      slack_url: "#",
      github_url: "#",
      version_tag: "C++ 03",
      first_boost_version: "1.66.0",
    }}
  />
);
NoImage.storyName = "No Image";

export const WithCallToAction = () => (
  <Pattern
    template="v3/includes/_hero_library.html"
    context={{
      title: "Boost.Beast",
      description: "Portable HTTP, WebSocket, and network operations.",
      cta_label: "Get started",
      cta_url: "#",
    }}
  />
);
WithCallToAction.storyName = "With Call To Action";
