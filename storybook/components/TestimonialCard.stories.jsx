import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Testimonial Card",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_testimonial_card.html"
    context={{
      heading: "What Engineers are saying",
      testimonials: [
        {
          quote:
            "I use Boost daily. I absolutely love it. It's wonderful. I could not do my job w/o it. Much of it is in the new C++11 standard too.",
          author: {
            name: "Name Surname",
            avatar_url: "/static/img/v3/demo_page/Avatar.png",
            role: "Contributor",
            role_badge: "/static/img/v3/demo_page/Badge.svg",
          },
        },
        {
          quote:
            "I use Boost daily. I absolutely love it. It's wonderful. I could not do my job w/o it. Much of it is in the new C++11 standard too.",
          author: {
            name: "Name Surname",
            avatar_url: "/static/img/v3/demo_page/Avatar.png",
            role: "Contributor",
            role_badge: "/static/img/v3/demo_page/Badge.svg",
          },
        },
        {
          quote:
            "I use Boost daily. I absolutely love it. It's wonderful. I could not do my job w/o it. Much of it is in the new C++11 standard too.",
          author: {
            name: "Name Surname",
            avatar_url: "/static/img/v3/demo_page/Avatar.png",
            role: "Contributor",
            role_badge: "/static/img/v3/demo_page/Badge.svg",
          },
        },
        {
          quote:
            "I use Boost daily. I absolutely love it. It's wonderful. I could not do my job w/o it. Much of it is in the new C++11 standard too.",
          author: {
            name: "Name Surname",
            avatar_url: "/static/img/v3/demo_page/Avatar.png",
            role: "Contributor",
            role_badge: "/static/img/v3/demo_page/Badge.svg",
          },
        },
      ],
    }}
  />
);
