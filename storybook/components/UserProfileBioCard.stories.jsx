import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/User Profile Bio Card",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_user_profile_bio_card.html"
    context={{
      title: "About",
      contributor_data: {
        Author: ["beast", "json"],
        Maintainer: ["asio"],
        Contributor: ["spirit", "asio", "beast", "filesystem", "algorithm"],
      },
      markdown:
        "Creator of Boost.Beast and Boost.JSON. C++ Alliance board member. Enjoys long-form networking talks.",
      button_url: "#",
      button_label: "Edit profile",
    }}
  />
);

export const Empty = () => (
  <Pattern
    template="v3/includes/_user_profile_bio_card.html"
    context={{ title: "About" }}
  />
);
