import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Downloads Table Card",
};

export const Default = () => (
  <Pattern
    template="v3/includes/_downloads_table_card.html"
    context={{
      downloads: {
        "Unix Variants": [
          {
            display_name: "boost_1_90_0.tar.bz2",
            url: "#",
            checksum: "a1b2c3d4e5f60718293a4b5c6d7e8f90112233445566778899aabbccddeeff",
          },
          {
            display_name: "boost_1_90_0.tar.gz",
            url: "#",
            checksum: "b2c3d4e5f60718293a4b5c6d7e8f90112233445566778899aabbccddeeff00",
          },
        ],
        Windows: [
          {
            display_name: "boost_1_90_0.zip",
            url: "#",
            checksum: "c3d4e5f60718293a4b5c6d7e8f90112233445566778899aabbccddeeff0011",
          },
        ],
      },
    }}
  />
);
