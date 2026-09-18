import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Pagination",
  argTypes: {
    pagination_current: { control: "number" },
    pagination_total: { control: "number" },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_pagination.html"
    context={{
      pagination_current: args.pagination_current,
      pagination_total: args.pagination_total,
    }}
  />
);
Default.args = { pagination_current: 3, pagination_total: 10 };

export const FirstPage = () => (
  <Pattern
    template="v3/includes/_pagination.html"
    context={{ pagination_current: 1, pagination_total: 10 }}
  />
);
FirstPage.storyName = "First page";

export const LastPage = () => (
  <Pattern
    template="v3/includes/_pagination.html"
    context={{ pagination_current: 10, pagination_total: 10 }}
  />
);
LastPage.storyName = "Last page";

export const ManyPages = () => (
  <Pattern
    template="v3/includes/_pagination.html"
    context={{ pagination_current: 12, pagination_total: 50 }}
  />
);
ManyPages.storyName = "Many pages (ellipsis)";

export const TwoPages = () => (
  <Pattern
    template="v3/includes/_pagination.html"
    context={{ pagination_current: 1, pagination_total: 2 }}
  />
);
TwoPages.storyName = "Two pages only";
