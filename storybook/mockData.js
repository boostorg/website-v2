// Shared mock data for Storybook stories.

export const DEMO_AUTHORS = [
  {
    name: "Vinnie Falco",
    profile_url: "#",
    role: "Author & Maintainer",
    avatar_url: "https://avatars.githubusercontent.com/u/1503976",
  },
  {
    name: "Chris Kohlhoff",
    profile_url: "#",
    role: "Contributor",
    avatar_url: "https://picsum.photos/seed/chris/80/80",
  },
  {
    name: "Peter Dimov",
    profile_url: "#",
    role: "Maintainer",
    avatar_url: "https://picsum.photos/seed/peter/80/80",
    badge: "star-tier-1",
    badge_label: "5 years",
  },
  {
    name: "Richard Thomson",
    profile_url: "#",
    role: "Contributor",
    avatar_url: "https://ui-avatars.com/api/?name=Richard+Thomson&size=48",
  },
  {
    name: "Alex Morgan",
    profile_url: "#",
    role: "Contributor",
    avatar_url: "https://ui-avatars.com/api/?name=Alex+Morgan&size=48",
  },
];

export const DEMO_AUTHOR = DEMO_AUTHORS[0];

export const DEMO_POSTS = [
  {
    title: "A talk by Richard Thomson at the Utah C++ Programmers Group",
    url: "#",
    date: "2025-03-03",
    category: "Issues",
    tag: "beast",
    author: DEMO_AUTHORS[3],
  },
  {
    title: "Boost.Bind and modern C++: a quick overview",
    url: "#",
    date: "2025-02-15",
    category: "Releases",
    tag: "bind",
    author: DEMO_AUTHORS[4],
  },
  {
    title: "C++ Alliance announces new Boost.JSON improvements",
    url: "#",
    date: "2025-01-20",
    category: "News",
    tag: "json",
    author: DEMO_AUTHORS[1],
  },
];

export const DEMO_EVENTS = [
  {
    title: "Boost 1.90.0 closed for major changes",
    description:
      "Release closed for major code changes. Still open for serious problem fixes and docs changes without release manager review.",
    date: "29/10/25",
    datetime: "2025-10-29",
    card_url: "#",
    card_aria_label: "Boost 1.90.0 closed for major changes",
  },
  {
    title: "C++ Now 2025 call for submissions",
    description: "C++ Now conference is accepting talk proposals until March 15.",
    date: "12/02/25",
    datetime: "2025-02-12",
    card_url: "#",
    card_aria_label: "C++ Now 2025 call for submissions",
  },
  {
    title: "Boost 1.89.0 released",
    description:
      "Boost 1.89.0 is available with updates to Asio, Beast, and several other libraries.",
    date: "15/01/25",
    datetime: "2025-01-15",
    card_url: "#",
    card_aria_label: "Boost 1.89.0 released",
  },
];

export const DEMO_BADGES = [
  { icon: "badge-tier-1", name: "Patch Wizard", earned_date: "08/08/2025" },
  { icon: "badge-tier-2", name: "Standard Bearer", earned_date: "03/07/2025" },
  { icon: "badge-tier-3", name: "Review Hawk", earned_date: "03/06/2025" },
  { icon: "boost-day", name: "Boost Day", earned_date: "01/06/2025" },
  { icon: "star-tier-1", name: "Library Alchemist", earned_date: "03/04/2025" },
  { icon: "badge-tier-5", name: "Code Whisperer", earned_date: "01/01/2025" },
];
