import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Achievement Card",
};

export const Empty = () => (
  <Pattern template="v3/includes/_achievement_card.html" context={{}} />
);

export const WithAchievements = () => (
  <Pattern
    template="v3/includes/_achievement_card.html"
    context={{
      achievements: [
        {
          title: "Lorem Ipsum",
          points: 22,
          description:
            "A longer description giving a summary of the achievement.",
        },
        {
          title: "Lorem Ipsum",
          points: 22,
          description:
            "A longer description giving a summary of the achievement.",
        },
        {
          title: "Lorem Ipsum",
          points: 22,
          description:
            "A longer description giving a summary of the achievement.",
        },
        {
          title: "Lorem Ipsum",
          points: 22,
          description:
            "A longer description giving a summary of the achievement.",
        },
      ],
      primary_button_url: "https://www.example.com",
    }}
  />
);
