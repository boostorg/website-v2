import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Install Card",
  argTypes: {
    title: { control: "text" },
    card_id: { control: "text" },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_install_card.html"
    context={{
      title: args.title,
      card_id: args.card_id,
      install_card_pkg_managers: [
        { label: "Conan", value: "conan", command: "conan install boost" },
        { label: "Vcpkg", value: "vcpkg", command: "vcpkg install boost" },
      ],
      install_card_system_install: [
        {
          label: "Ubuntu",
          value: "ubuntu",
          command: "sudo apt install libboost-all-dev",
        },
        {
          label: "Fedora",
          value: "fedora",
          command: "sudo dnf install boost-devel",
        },
        {
          label: "CentOS",
          value: "centos",
          command: "sudo yum install boost-devel",
        },
        { label: "Arch", value: "arch", command: "sudo pacman -S boost" },
        {
          label: "Homebrew",
          value: "homebrew",
          command: "brew install boost",
        },
      ],
    }}
  />
);
Default.args = {
  title: "Install Boost and get started in your terminal.",
  card_id: "install-1",
};
