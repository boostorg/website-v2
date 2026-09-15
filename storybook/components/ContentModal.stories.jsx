import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Content Modal",
};

export const Default = () => (
  <div>
    <button
      className="btn btn-primary"
      onClick={(e) => {
        e.preventDefault();
        window.location.hash = "content-modal-demo";
      }}
    >
      Open modal
    </button>
    <Pattern
      template="v3/includes/_content_modal.html"
      context={{
        modal_id: "content-modal-demo",
        title: "Release Notes",
        subtitle: "Boost 1.90.0",
        content:
          "<p>This release adds several new libraries and fixes a number of long-standing bugs across the collection.</p><p>See the full changelog for details.</p>",
      }}
    />
  </div>
);

export const WithNavigation = () => (
  <div>
    <button
      className="btn btn-primary"
      onClick={(e) => {
        e.preventDefault();
        window.location.hash = "content-modal-nav-demo";
      }}
    >
      Open modal
    </button>
    <Pattern
      template="v3/includes/_content_modal.html"
      context={{
        modal_id: "content-modal-nav-demo",
        title: "Release Notes",
        subtitle: "Boost 1.89.0",
        content: "<p>Middle entry in a series - both prev and next are enabled.</p>",
        prev_url: "#content-modal-nav-demo",
        next_url: "#content-modal-nav-demo",
      }}
    />
  </div>
);
WithNavigation.storyName = "With Navigation";
