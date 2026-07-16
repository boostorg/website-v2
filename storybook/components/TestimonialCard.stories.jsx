import React from "react";
import { Pattern } from "storybook-django/src/react";
import { DEMO_AUTHORS } from "../mockData";

const TESTIMONIALS = [
  {
    quote:
      "I use Boost daily. I absolutely love it. Much of it is now in the C++ standard. It's a treasure chest of well-reviewed, portable code.",
    author: DEMO_AUTHORS[0],
  },
  {
    quote:
      "Boost.Asio completely changed how I think about async I/O. The proactor pattern makes complex networking code manageable and correct.",
    author: DEMO_AUTHORS[1],
  },
  {
    quote:
      "The peer review process guarantees a level of quality you rarely find in open-source libraries. Boost is C++ done right.",
    author: DEMO_AUTHORS[2],
  },
  {
    quote:
      "Boost.Spirit is a marvel. Writing parsers as PEGs directly in C++ type system - mind-blowing when I first saw it.",
    author: DEMO_AUTHORS[3],
  },
];

export default {
  title: "Components/Testimonial Card",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_testimonial_card.html"
    context={{
      heading: "What engineers are saying",
      testimonials: TESTIMONIALS,
    }}
  />
);

export const SingleTestimonial = () => (
  <Pattern
    template="v3/includes/_testimonial_card.html"
    context={{
      heading: "What engineers are saying",
      testimonials: [TESTIMONIALS[0]],
    }}
  />
);
SingleTestimonial.storyName = "Single testimonial (no carousel)";
