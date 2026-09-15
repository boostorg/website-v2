import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Content Modal Group",
};

const DEMO_ITEMS = [
  {
    slug: "content-modal-group-1",
    title: "Boost 1.90.0",
    content: "<p>Adds several new libraries and fixes long-standing bugs.</p>",
    prev_url: "",
    next_url: "#content-modal-group-2",
  },
  {
    slug: "content-modal-group-2",
    title: "Boost 1.89.0",
    content: "<p>Performance improvements across the networking libraries.</p>",
    prev_url: "#content-modal-group-1",
    next_url: "#content-modal-group-3",
  },
  {
    slug: "content-modal-group-3",
    title: "Boost 1.88.0",
    content: "<p>Initial release of Boost.JSON improvements.</p>",
    prev_url: "#content-modal-group-2",
    next_url: "",
  },
];

export const Default = () => (
  <div>
    <button
      className="btn btn-primary"
      onClick={(e) => {
        e.preventDefault();
        window.location.hash = DEMO_ITEMS[0].slug;
      }}
    >
      Open first modal
    </button>
    <Pattern
      template="v3/includes/_content_modal_group.html"
      context={{ items: DEMO_ITEMS }}
    />
  </div>
);
