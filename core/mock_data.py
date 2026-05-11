from datetime import date

from django.conf import settings
from django.utils.text import slugify

from core.constants import BadgeToken, SLACK_MEMBER_COUNT
from core.templatetags.custom_static import large_static
from libraries.utils import commit_data_to_stats_bars


def _with_carousel_nav(items, slug_key="title"):
    """Annotate each item with `slug`, `prev_url`, `next_url` for in-page
    carousel/modal navigation. Navigation wraps cyclically: the first item's
    `prev_url` points to the last item, and the last item's `next_url`
    points to the first.
    """
    slugs = [slugify(item[slug_key]) for item in items]
    n = len(items)
    return [
        {
            **item,
            "slug": slugs[i],
            "prev_url": f"#{slugs[(i - 1) % n]}",
            "next_url": f"#{slugs[(i + 1) % n]}",
        }
        for i, item in enumerate(items)
    ]


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
                "badge": BadgeToken.TIER_3,
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
                "badge": BadgeToken.TIER_1,
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
            "description": f"Tap into quick answers, networking, and chat with {SLACK_MEMBER_COUNT} members.",
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

    # Each testimonial bundles both the carousel-card snippet (quote, author)
    # AND the full long-form content for the Content Modal that opens when
    # the quote is clicked. The slug is derived once here from the title and
    # used by both the testimonial card and the bundled modal group, so every
    # consumer (Homepage, demo page, etc.) gets the wiring for free.
    _raw_testimonials = [
        {
            "title": ("Powering Cognitive Communications Engine for NASA with Boost"),
            "subtitle": ("By Prof. Sven G. Bilén, Ph.D., Timothy M. Hackett, Ph.D."),
            "quote": (
                "When you're building software that needs to operate "
                "flawlessly with the limited flight pass opportunities of "
                "the International Space Station, you need libraries you "
                "can trust and that allow you to move quickly."
            ),
            "author": {
                "name": "Prof. Sven G. Bilén, Ph.D.",
                "profile_url": "#",
                "avatar_url": large_static("img/v3/demo_page/avatar.png"),
                "role": "The Pennsylvania State University",
                "badge": BadgeToken.TIER_3,
            },
            "content": """
<h2>The Challenge: Building a Cognitive Engine for Space</h2>
<p>Our research team at Penn State, in collaboration with Worcester
Polytechnic Institute and NASA's John H. Glenn Research Center, set out to
build something that had never been deployed in a real space system before:
a multi-objective reinforcement-learning cognitive engine capable of
autonomously optimizing radio communications aboard the International Space
Station. The engine used deep neural network ensembles to manage radio
resource allocation in real time, adjusting modulation and coding schemes,
roll-off factors, and transmit power to simultaneously optimize six
competing objectives: bit error rate, throughput, occupied bandwidth,
spectral efficiency, transmit power efficiency, and DC power consumption.</p>
<p>We wrote the engine in C++11 for maximum portability between ground-based
and space-based radio platforms. Unlike our original MATLAB prototypes, C++
does not come equipped with high-level constructs for networking,
serialization, or matrix algebra. We needed production-quality libraries
that could handle real-time UDP communications with commercial DVB-S2
satellite modems and allow us to save and restore the complete state of a
learning system between orbital passes, all while meeting the strict
licensing constraints imposed by ITAR and export control regulations.</p>

<h2>Why Boost: Licensing, Reliability, and Portability</h2>
<p>Choosing the right software libraries was one of the most consequential
decisions in the entire project. Because our export-controlled software was
destined for redistribution on NASA's STRS (Space Telecommunications Radio
System) Repository, we required libraries with permissive, non-copyleft
licenses. GPL and LGPL libraries were off the table. This constraint alone
eliminated the majority of candidates.</p>
<p>Boost stood out immediately. Its permissive license meant we could
integrate it into our cognitive engine and contribute the code to the STRS
Repository without any risk of violating redistribution requirements. But
licensing was only the starting point. What truly set Boost apart was the
maturity and reliability of its libraries. When you are building a system
that will operate on the International Space Station, you cannot afford to
debug flaky networking or unreliable serialization code. Boost gave us
battle-tested components that worked.</p>

<h2>Boost.Asio: The Communications Backbone</h2>
<p>Our cognitive engine communicates with multiple external modems
simultaneously. The ViaSat DVB-S2 receiver sends real-time signal quality
telemetry over UDP, while the ML605 transmitter modem requires raw Ethernet
frames to embed action tuples into Advanced Orbiting Systems (AOS) frames
for uplink to the ISS. Each interface has different protocol requirements,
different timing constraints, and different failure modes.</p>
<p>Boost.Asio handled all of this elegantly. Its asynchronous I/O model
allowed us to manage concurrent UDP listeners and transmitters without
resorting to low-level socket programming or platform-specific APIs. The
abstraction layer meant that the same networking code we developed on our
ground workstations could be ported to different target platforms with
minimal modification. For a system that must operate reliably within a
40-millisecond round-trip time window between ground and orbit, the
deterministic performance of Boost.Asio was critical.</p>

<h2>Boost.Serialization: Preserving Learned Intelligence Across Orbital Passes</h2>
<p>One of the key research questions in our experiment was whether a
cognitive engine that retains its learned neural network weights from a
previous ground station pass outperforms one that must relearn from scratch
at the beginning of every contact window. Each ISS pass over a ground
station lasts only minutes, and every second spent relearning is a second
of suboptimal communications performance.</p>
<p>Boost.Serialization made it possible to archive and restore the complete
state of our reinforcement-learning system, including all neural network
weights, the training buffer contents, and application-specific parameters,
to human-readable text files. When the engine restarts for a new pass, it
can load the serialized state and resume with full knowledge of what it
previously learned. This capability is foundational to the entire concept
of persistent cognitive communications: a radio that gets smarter over
time, pass after pass. The library's ability to serialize complex, nested
C++ object hierarchies transparently saved us weeks of development time
that would otherwise have been spent writing custom persistence code.</p>

<h2>Boost as Part of the Broader Ecosystem</h2>
<p>Boost's influence on our project extended beyond the two libraries we
used directly. MLPack, the machine learning library we selected for our
neural network implementation, uses Boost internally. Armadillo, our matrix
algebra library, also integrates with the Boost ecosystem. This meant that
our entire software stack shared a common foundation, which simplified the
build process, reduced dependency conflicts, and made the system more
maintainable. When multiple critical libraries in your project all trust
Boost as their own dependency, that tells you something important about
its quality and standing in the C++ community.</p>

<h2>Impact and Results</h2>
<p>Our implemented cognitive engine completed on-orbit experiments with the
ISS via the SCaN Testbed in May 2017. The cognitive engine was tested
through a total of 20 flight passes over NASA Glenn Research Center's
ground station providing performance results across a variety of link
profiles. To the best of our knowledge, this marked one of the first
published experiments of using a cognitive engine with a space-based asset
and demonstrated that reinforcement learning-based multi-objective
optimization is both feasible as well as useful for satellite
communications.</p>
<p>The modular, object-oriented architecture we built was designed so that
only the application-specific module needs to be swapped to adapt the
engine for entirely different missions or optimization objectives. This
reusability was central to NASA's vision for cognitive communications:
systems that can be deployed across diverse missions without requiring a
complete software rewrite each time.</p>
<p>Boost helped our small academic-government research team to punch well
above our weight. Instead of spending months building and testing
networking and serialization infrastructure from scratch, we were able to
focus on what made our project unique: the cognitive algorithms themselves.
For any team building mission-critical C++ systems under tight timelines
and strict licensing constraints, Boost is not just a convenience, it is a
force multiplier.</p>

<blockquote>
<p>When you're building software that needs to operate flawlessly with the
limited flight pass opportunities of the International Space Station, you
need libraries you can rely on. Boost delivered production-grade tools with
licensing compliant to NASA requirements, enabling our team to prioritize
the science.</p>
<p>&mdash; Prof. Sven G. Bilén, The Pennsylvania State University</p>
</blockquote>
""",
        },
        {
            "title": "Lorem ipsum dolor sit amet",
            "subtitle": "By Ipsum Loremson",
            "quote": "Lorem ipsum content to test short testimonial",
            "author": {
                "name": "Ipsum Loremson",
                "profile_url": "#",
                "avatar_url": large_static("img/v3/demo-page/avatar.png"),
                "role": "Maintainer",
                "badge": BadgeToken.TIER_3,
            },
        },
        {
            "quote": "3 — Every serious C++ codebase I've worked on has leaned on Boost in some way. It's the proving ground where tomorrow's standard library takes shape.",
            "author": {
                "name": "Linus Torvalds",
                "profile_url": "#",
                "avatar_url": large_static("img/v3/demo-page/avatar.png"),
                "role": "Reviewer",
                "badge": BadgeToken.TIER_3,
            },
        },
        {
            "quote": "4 — Contributing to Boost taught me more about writing portable, peer-reviewed C++ than any textbook ever could.",
            "author": {
                "name": "Margaret Hamilton",
                "profile_url": "#",
                "avatar_url": large_static("img/v3/demo-page/avatar.png"),
                "role": "Contributor",
                "badge": BadgeToken.TIER_3,
            },
            "content": """
<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
consequat.</p>

<p>Duis aute irure dolor in reprehenderit in voluptate velit esse cillum
dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non
proident, sunt in culpa qui officia deserunt mollit anim id est laborum.</p>
""",
        },
    ]
    testimonials = _with_carousel_nav(_raw_testimonials)

    library_intro = {
        "library_name": "Boost.Core.",
        "description": "Lightweight utilities that power dozens of other Boost libraries",
        "authors": [
            {
                "name": "Vinnie Falco",
                "role": "Author",
                "avatar_url": large_static("img/v3/demo-page/avatar.png"),
                "badge": BadgeToken.TIER_3,
                "bio": "Big C++ fan. Not quite kidney-donation level, but close.",
            },
            {
                "name": "Alex Wells",
                "role": "Contributor",
                "avatar_url": large_static("img/v3/demo-page/avatar.png"),
                "bio": "C++ enthusiast who has worked at Intel and Microsoft.",
            },
            {
                "name": "Dave Abrahams",
                "role": "Maintainer",
                "avatar_url": large_static("img/v3/demo-page/avatar.png"),
                "badge": BadgeToken.TIER_3,
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

    hero_legacy_image_url_light = large_static("img/v3/home-page/heros.png")

    hero_legacy_image_url_dark = large_static("img/v3/home-page/heros_light.png")

    hero_image_url = large_static("img/v3/home-page/home-page-foreground.png")
    hero_image_url_light = large_static("img/v3/home-page/home-page-foreground.png")
    hero_image_url_dark = large_static("img/v3/home-page/home-page-foreground.png")

    library_about_code = (
        "int main()\n"
        "{\n"
        "    net::io_context ioc;\n"
        "    tcp::resolver resolver(ioc);\n"
        "    beast::tcp_stream stream(ioc);\n"
        "\n"
        '    stream.connect(resolver.resolve("example.com", "80"));\n'
        "\n"
        '    http::request<http::empty_body> req{http::verb::get, "/", 11};\n'
        '    req.set(http::field::host, "example.com");\n'
        "\n"
        "    http::write(stream, req);\n"
        "\n"
        "    beast::flat_buffer buffer;\n"
        "    http::response<http::string_body> res;\n"
        "    http::read(stream, buffer, res);\n"
        "\n"
        "    std::cout << res << std::endl;\n"
        "}"
    )

    library_install_code = (
        "brew install openssl\n"
        "export OPENSSL_ROOT=$(brew --prefix openssl)\n"
        "# install bjam tool user specific configuration file to read OPENSSL_ROOT\n"
        "# see https://www.bfgroup.xyz/b2/manual/release/index.html\n"
        "cp ./libs/beast/tools/user-config.jam $HOME"
    )

    library_release_contributors = [
        {
            "name": "Eric Niebler",
            "profile_url": "#",
            "role": "Author",
            "avatar_url": "https://ui-avatars.com/api/?name=Eric+Niebler&size=48",
            "badge_url": BadgeToken.TIER_2,
        },
        {
            "name": "Marshall Clow",
            "profile_url": "#",
            "role": "Maintainer",
            "avatar_url": "https://ui-avatars.com/api/?name=Marshall+Clow&size=48",
            "badge_url": BadgeToken.TIER_1,
        },
        {
            "name": "Glen Fernandes",
            "profile_url": "#",
            "role": "New Contributor",
            "avatar_url": "https://ui-avatars.com/api/?name=Glen+Fernandes&size=48",
            "badge_url": BadgeToken.STAR_TIER_1,
        },
        {
            "name": "Frank Little",
            "profile_url": "#",
            "role": "New Contributor",
            "avatar_url": "https://ui-avatars.com/api/?name=Frank+Little&size=48",
            "badge_url": BadgeToken.TIER_2,
        },
        {
            "name": "Mike Leslie",
            "profile_url": "#",
            "role": "Contributor",
            "avatar_url": "https://ui-avatars.com/api/?name=Mike+Leslie&size=48",
            "badge_url": BadgeToken.TIER_3,
        },
        {
            "name": "Peter Dimov",
            "profile_url": "#",
            "role": "Author",
            "avatar_url": "https://ui-avatars.com/api/?name=Peter+Dimov&size=48",
            "badge_url": BadgeToken.STAR_TIER_1,
        },
        {
            "name": "Andrew Jameson",
            "profile_url": "#",
            "role": "Contributor",
            "avatar_url": "https://ui-avatars.com/api/?name=Andrew+Jameson&size=48",
            "badge_url": BadgeToken.TIER_3,
        },
    ]

    library_all_contributors = [
        {
            "name": "Eric Niebler",
            "profile_url": "#",
            "role": "Author",
            "avatar_url": "https://ui-avatars.com/api/?name=Eric+Niebler&size=48",
            "badge_url": BadgeToken.TIER_1,
        },
        {
            "name": "Peter Dimov",
            "profile_url": "#",
            "role": "Author",
            "avatar_url": "https://ui-avatars.com/api/?name=Peter+Dimov&size=48",
            "badge_url": BadgeToken.TIER_1,
        },
        {
            "name": "Vinnie Falco",
            "profile_url": "#",
            "role": "Author",
            "avatar_url": "https://ui-avatars.com/api/?name=Vinnie+Falco&size=48",
            "badge_url": BadgeToken.TIER_2,
        },
        {
            "name": "Marshall Clow",
            "profile_url": "#",
            "role": "Maintainer",
            "avatar_url": "https://ui-avatars.com/api/?name=Marshall+Clow&size=48",
            "badge_url": BadgeToken.TIER_1,
        },
        {
            "name": "Andrew Jameson",
            "profile_url": "#",
            "role": "Contributor",
            "avatar_url": "https://ui-avatars.com/api/?name=Andrew+Jameson&size=48",
            "badge_url": BadgeToken.STAR_TIER_1,
        },
        {
            "name": "Glen Fernandes",
            "profile_url": "#",
            "role": "New Contributor",
            "avatar_url": "https://ui-avatars.com/api/?name=Glen+Fernandes&size=48",
            "badge_url": BadgeToken.TIER_1,
        },
        {
            "name": "Frank Little",
            "profile_url": "#",
            "role": "New Contributor",
            "avatar_url": "https://ui-avatars.com/api/?name=Frank+Little&size=48",
            "badge_url": BadgeToken.TIER_1,
        },
        {
            "name": "Mike Leslie",
            "profile_url": "#",
            "role": "Contributor",
            "avatar_url": "https://ui-avatars.com/api/?name=Mike+Leslie&size=48",
            "badge_url": BadgeToken.TIER_2,
        },
    ]
