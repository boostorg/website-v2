from datetime import date

from django.conf import settings

from libraries.utils import commit_data_to_stats_bars


class SharedResources:
    demo_posts = [
        {
            "title": "A talk by Richard Thomson at the Utah C++ Programmers Group",
            "url": "#",
            "date": date(2025, 3, 3),
            "category": "Issues",
            "tag": "beast",
            "author": {
                "name": "Richard Thomson",
                "profile_url": "#",
                "role": "Contributor",
                "avatar_url": "https://ui-avatars.com/api/?name=Richard+Thomson&size=48",
                "badge": "badge-gold",
            },
        },
        {
            "title": "A talk by Richard Thomson at the Utah C++ Programmers Group",
            "url": "#",
            "date": date(2025, 3, 3),
            "category": "Issues",
            "tag": "beast",
            "author": {
                "name": "Peter Dimov",
                "profile_url": "#",
                "role": "Maintainer",
                "avatar_url": "https://ui-avatars.com/api/?name=Peter+Dimov&size=48",
                "badge": "badge-bronze",
            },
        },
        {
            "title": "Boost.Bind and modern C++: a quick overview",
            "url": "#",
            "date": date(2025, 2, 15),
            "category": "Releases",
            "tag": "bind",
            "author": {
                "name": "Alex Morgan",
                "profile_url": "#",
                "role": "Contributor",
                "avatar_url": "https://thispersondoesnotexist.com/",
            },
        },
        {
            "title": "Boost.Bind and modern C++: a quick overview again",
            "url": "#",
            "date": date(2025, 2, 15),
            "category": "Releases",
            "tag": "bind",
            "author": {
                "name": "Alex Morgan",
                "profile_url": "#",
                "role": "Contributor",
                "avatar_url": "https://thispersondoesnotexist.com/",
            },
        },
        {
            "title": "utility::string_view and core::detail::string_view",
            "url": "#",
            "date": date(2025, 2, 15),
            "category": "Releases",
            "tag": "bind",
            "author": {
                "name": "Alex Morgan",
                "profile_url": "#",
                "role": "Contributor",
                "avatar_url": "https://thispersondoesnotexist.com/",
            },
        },
    ]

    install_card_pkg_managers = [
        {"label": "Conan", "value": "conan", "command": "conan install boost"},
        {"label": "Vcpkg", "value": "vcpkg", "command": "vcpkg install boost"},
    ]

    install_card_system_install = [
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

    popular_terms = [
        {"label": "Networking"},
        {"label": "Math"},
        {"label": "Data processing"},
        {"label": "Concurrency"},
        {"label": "File systems"},
        {"label": "Testing"},
    ]

    demo_events = [
        {
            "title": "Boost 1.90.0 closed for major changes",
            "description": "Release closed for major code changes. "
            "Still open for serious problem fixes.",
            "date": "29/10/25",
            "datetime": "2025-10-29",
        },
        {
            "title": "C++ Now 2025 call for submissions",
            "description": "C++ Now conference is accepting talk proposals "
            "until March 15.",
            "date": "12/02/25",
            "datetime": "2025-02-12",
        },
        {
            "title": "Boost 1.89.0 released",
            "description": "Boost 1.89.0 is available with updates to Asio, "
            "Beast, and several other libraries.",
            "date": "15/01/25",
            "datetime": "2025-01-15",
        },
        {
            "title": "Boost 1.89.0 released",
            "description": "Boost 1.89.0 is available with updates to Asio, "
            "Beast, and several other libraries.",
            "date": "15/01/25",
            "datetime": "2025-01-15",
        },
    ]

    demo_events_with_links = [
        {
            **event,
            "card_url": f"#event-{i}",
            "card_aria_label": event["title"],
        }
        for i, event in enumerate(demo_events)
    ]

    code_demo_hello = """#include <iostream>
int main()
{
    std::cout << "Hello, Boost.";
}"""

    demo_join_community_links = 4 * [
        {
            "title": "Get help",
            "url": "#",
            "description": "Tap into quick answers, networking, and chat with 24,000+ members.",
            "icon_name": "github",
        }
    ]

    example_commit_data = [
        {"release": "1.71.0", "commit_count": 106},
        {"release": "1.72.0", "commit_count": 70},
        {"release": "1.73.0", "commit_count": 65},
        {"release": "1.74.0", "commit_count": 60},
        {"release": "1.75.0", "commit_count": 36},
        {"release": "1.76.0", "commit_count": 31},
        {"release": "1.77.0", "commit_count": 15},
        {"release": "1.78.0", "commit_count": 17},
        {"release": "1.79.0", "commit_count": 22},
        {"release": "1.80.0", "commit_count": 2},
        {"release": "1.81.0", "commit_count": 76},
        {"release": "1.82.0", "commit_count": 32},
        {"release": "1.83.0", "commit_count": 3},
        {"release": "1.84.0", "commit_count": 35},
        {"release": "1.85.0", "commit_count": 41},
        {"release": "1.86.0", "commit_count": 42},
        {"release": "1.87.0", "commit_count": 27},
        {"release": "1.88.0", "commit_count": 28},
        {"release": "1.89.0", "commit_count": 15},
        {"release": "1.90.0", "commit_count": 18},
    ]

    example_library_commits_bars = commit_data_to_stats_bars(
        example_commit_data[-10:]
        if len(example_commit_data) > 10
        else example_commit_data
    )

    testimonials = [
        {
            "quote": "I use Boost daily. I absolutely love it. It's wonderful. I could not do my job w/o it. Much of it is in the new C++11 standard too.",
            "author": {
                "name": "Name Surname",
                "profile_url": "#",
                "avatar_url": "/static/img/v3/demo_page/Avatar.png",
                "role": "Contributor",
                "badge": "badge-gold",
            },
        },
        {
            "quote": "I use Boost daily. I absolutely love it. It's wonderful. I could not do my job w/o it. Much of it is in the new C++11 standard too.",
            "author": {
                "name": "Name Surname",
                "profile_url": "#",
                "avatar_url": "/static/img/v3/demo_page/Avatar.png",
                "role": "Contributor",
                "badge": "badge-gold",
            },
        },
        {
            "quote": "I use Boost d1aily. I absolutely love it. It's wonderful. I could not do my job w/o it. Much of it is in the new C++11 standard too.",
            "author": {
                "name": "Name Surname",
                "profile_url": "#",
                "avatar_url": "/static/img/v3/demo_page/Avatar.png",
                "role": "Contributor",
                "badge": "badge-gold",
            },
        },
        {
            "quote": "I use Boost daily. I absolutely love it. It's wonderful. I could not do my job w/o it. Much of it is in the new C++11 standard too.",
            "author": {
                "name": "Name Surname",
                "profile_url": "#",
                "avatar_url": "/static/img/v3/demo_page/Avatar.png",
                "role": "Contributor",
                "badge": "badge-gold",
            },
        },
    ]

    library_intro = {
        "library_name": "Boost.Core.",
        "description": "Lightweight utilities that power dozens of other Boost libraries",
        "authors": [
            {
                "name": "Vinnie Falco",
                "role": "Author",
                "avatar_url": f"{settings.STATIC_URL}img/v3/demo_page/Avatar.png",
                "badge": "badge-gold",
                "bio": "Big C++ fan. Not quite kidney-donation level, but close.",
            },
            {
                "name": "Alex Wells",
                "role": "Contributor",
                "avatar_url": f"{settings.STATIC_URL}img/v3/demo_page/Avatar.png",
                "bio": "C++ enthusiast who has worked at Intel and Microsoft.",
            },
            {
                "name": "Dave Abrahams",
                "role": "Maintainer",
                "avatar_url": f"{settings.STATIC_URL}img/v3/demo_page/Avatar.png",
                "badge": "badge-gold",
                "bio": "Contributor to Boost since 2009.",
            },
        ],
        "cta_url": "#",
    }

    build_anything_with_boost = {
        "title": "Build anything with Boost",
        "text": "Use, modify, and distribute Boost libraries freely. No binary attribution needed.",
        "image_url": f"{settings.STATIC_URL}img/checker.png",
        "image_alt": "This is a placeholder image",
        "button_url": "#",
        "button_label": "See license details",
    }

    hero_legacy_image_url_light = f"{settings.STATIC_URL}img/v3/home-page/heros.png"

    hero_legacy_image_url_dark = (
        f"{settings.STATIC_URL}img/v3/home-page/heros_light.png"
    )

    hero_image_url = f"{settings.STATIC_URL}img/v3/home-page/home-page-foreground.png"
    hero_image_url_light = (
        f"{settings.STATIC_URL}img/v3/home-page/home-page-foreground.png"
    )
    hero_image_url_dark = (
        f"{settings.STATIC_URL}img/v3/home-page/home-page-foreground.png"
    )
