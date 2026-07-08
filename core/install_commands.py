"""Install command lists rendered by `v3/includes/_install_card.html`.

Each entry is `{label, value, command}`: `label` is the tab name, `value` is
the radio/CSS state key, `command` is the shell command shown to the user.
"""

INSTALL_PKG_MANAGERS = [
    {"label": "Conan", "value": "conan", "command": "conan install boost"},
    {"label": "Vcpkg", "value": "vcpkg", "command": "vcpkg install boost"},
]

INSTALL_SYSTEM_INSTALL = [
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
