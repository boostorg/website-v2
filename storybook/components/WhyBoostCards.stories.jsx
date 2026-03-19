import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Why Boost Cards",
};

const Card = ({ title, description, icon_name }) => (
  <Pattern
    template="v3/includes/_content_detail_card_item.html"
    context={{ title, description, icon_name }}
  />
);

export const Grid = () => (
  <section className="why-boost-cards" aria-labelledby="why-boost-heading">
    <h2 id="why-boost-heading" className="why-boost-cards__heading">
      Why Boost?
    </h2>
    <div className="why-boost-cards__grid">
      <Card
        title="Get help"
        description="Tap into quick answers, networking, and chat with 24,000+ members."
        icon_name="bullseye-arrow"
      />
      <Card
        title="Documentation"
        description="Browse library docs, examples, and release notes in one place."
        icon_name="link"
      />
      <Card
        title="Community"
        description="Mailing lists, GitHub, and community guidelines for contributors."
        icon_name="human"
      />
      <Card
        title="Releases"
        description="Latest releases, download links, and release notes."
        icon_name="info-box"
      />
      <Card
        title="Learn"
        description="Access documentation, books, and courses to level up your C++."
        icon_name="bullseye-arrow"
      />
      <Card
        title="Contribute"
        description="Report issues, submit patches, and join the community."
        icon_name="bullseye-arrow"
      />
      <Card
        title="Stay updated"
        description="Releases, news, and announcements from the Boost community."
        icon_name="bullseye-arrow"
      />
      <Card
        title="Libraries"
        description="Portable, peer-reviewed libraries for a wide range of use cases."
        icon_name="bullseye-arrow"
      />
      <Card
        title="Standards"
        description="Many Boost libraries have been adopted into the C++ standard."
        icon_name="bullseye-arrow"
      />
      <Card
        title="Quality"
        description="Peer-reviewed code and documentation maintained by the community."
        icon_name="bullseye-arrow"
      />
      <Card
        title="Cross-platform"
        description="Libraries designed to work across compilers and platforms."
        icon_name="bullseye-arrow"
      />
    </div>
  </section>
);
