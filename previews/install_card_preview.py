from django_lookbook.preview import LookbookPreview
from django.template.loader import render_to_string


INSTALL_CARD_PKG_MANAGERS = [
    {"label": "Conan", "value": "conan", "command": "conan install boost"},
    {"label": "Vcpkg", "value": "vcpkg", "command": "vcpkg install boost"},
]

INSTALL_CARD_SYSTEM_INSTALL = [
    {
        "label": "Ubuntu",
        "value": "ubuntu",
        "command": "sudo apt install libboost-all-dev",
    },
    {
        "label": "Fedora",
        "value": "fedora",
        "command": "sudo dnf install boost-devel",
    },
    {
        "label": "CentOS",
        "value": "centos",
        "command": "sudo yum install boost-devel",
    },
    {"label": "Arch", "value": "arch", "command": "sudo pacman -S boost"},
    {"label": "Homebrew", "value": "homebrew", "command": "brew install boost"},
]


class InstallCardPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Install card with tabbed installation methods and dynamic command display.

        Template: `v3/includes/_install_card.html`

        | Variable | Required | Description |
        |---|---|---|
        | `title` | No | Card heading. Default: "Install Boost and get started in your terminal." |
        | `install_card_pkg_managers` | Yes | List of dicts with: label, value, command |
        | `install_card_system_install` | Yes | List of dicts with: label, value, command |
        """
        return render_to_string(
            "v3/includes/_install_card.html",
            {
                "title": "Install Boost and get started in your terminal.",
                "install_card_pkg_managers": INSTALL_CARD_PKG_MANAGERS,
                "install_card_system_install": INSTALL_CARD_SYSTEM_INSTALL,
            },
        )
