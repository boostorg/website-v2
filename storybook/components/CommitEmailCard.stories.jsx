import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Commit Email Card",
};

export const Empty = () => (
  <Pattern
    template="v3/includes/_commit_email_card.html"
    context={{ commit_email_addresses: [] }}
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
    }}
  />
);
