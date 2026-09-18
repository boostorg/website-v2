import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Commit Email Card",
};

export const Empty = () => (
  <Pattern
    template="v3/includes/_commit_email_card.html"
    context={{
      commit_email_addresses: [],
      commit_email_form: { commit_email: { value: "", errors: [] } },
    }}
  />
);

export const WithAddresses = () => (
  <Pattern
    template="v3/includes/_commit_email_card.html"
    context={{
      commit_email_addresses: [
        { pk: 1, email: "vinnie.falco@example.com", claim_verified: true },
        { pk: 2, email: "vfalco@work-example.com", claim_verified: false },
      ],
      commit_email_form: { commit_email: { value: "", errors: [] } },
    }}
  />
);

export const WithError = () => (
  <Pattern
    template="v3/includes/_commit_email_card.html"
    context={{
      commit_email_addresses: [],
      commit_email_form: {
        commit_email: {
          value: "not-an-email",
          errors: ["Enter a valid email address."],
        },
      },
    }}
  />
);
