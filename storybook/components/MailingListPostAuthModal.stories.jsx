import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Mailing List Post Auth Modal",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_mailing_list_post_auth_modal.html"
    context={{
      post_auth_modal_subscribe_url: "#",
      post_auth_modal_user_email: "vinnie.falco@example.com",
      post_auth_modal_mailing_lists: [
        {
          id: 1,
          name: "Boost Announce",
          address: "boost-announce@lists.boost.org",
          description: "Low-volume list for release and security announcements.",
        },
        {
          id: 2,
          name: "Boost Users",
          address: "boost-users@lists.boost.org",
          description: "General discussion for people using Boost libraries.",
        },
        {
          id: 3,
          name: "Boost Developers",
          address: "boost@lists.boost.org",
          description: "Discussion for people developing and maintaining Boost.",
        },
      ],
    }}
  />
);
