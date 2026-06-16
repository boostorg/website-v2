# Popular Search Terms on the V3 Homepage

The V3 homepage search card shows a row of "popular term" keyword badges. Each keyword badge is a clickable shortcut that pre-fills the site search. The keyword badges come from what real users are actually searching for on boost.org, filtered automatically so admins don't have to clean up typos and gibberish by hand.

## Where the data comes from

Algolia powers boost.org's site search. As a side effect, Algolia records every query users type. Once a week the site asks Algolia for the most popular queries over the **previous two weeks** against the current live release's documentation index. The two-week window overlaps the weekly cadence by one week, so a term spiking on Monday doesn't drop off the homepage the moment its peak rolls past. The fetch asks Algolia for click analytics so each candidate also carries the number of results the query matched.

## How the list is cleaned up

Searches that returned **no results** are dropped first — a query Algolia matched nothing for would only be a dead-end shortcut on the homepage, so it never becomes a keyword badge no matter how often it was typed.

The remaining raw output from Algolia contains a lot of noise — incomplete words like `asi` or `filesyste`, personal names, single-letter queries. Before anything is written to the database, an LLM reviews each candidate and decides KEEP or REJECT.

The LLM is given a few helpful hints:

- Concrete examples of what to reject (typos, gibberish, names, test inputs) and what to keep (library names, technical concepts, domain topics).
- The full list of flagship and core Boost library names — anything matching a real library is always KEEP, even if the name looks unusual in isolation (e.g., `asio`, `lockfree`, `beast`).
- A rule to return lowercase display labels, preserving technical identifiers like `boost_check_equal` verbatim.

Whatever survives this check is what shows up on the homepage. There is no admin approval step — the LLM is the quality gate.

## How the keyword badges are ordered

Chips are ordered first by how often the term was searched. When two terms tie on search count, **a known Boost library name ranks above a generic term**. So if "asio" and "performance" were searched the same number of times, "asio" gets the higher slot. Alphabetical order breaks any remaining ties.

Pinned rows (rows with the **Pinned?** checkbox ticked in admin) sit above all Algolia-derived rows regardless of search count. When more than one row is pinned, they order amongst themselves by `rank` — set `rank=1` on the row you want first, `rank=2` next, and so on.

## Admin overrides

Three escape hatches let curators correct the LLM's decisions:

- **Move to exclusions** — if the LLM kept a term you don't want shown, select it in admin and run "Move selected to exclusions (homepage banlist)". The keyword badge disappears from the homepage immediately, and future refreshes will skip the term too.
- **Manual pin** — if the LLM rejected something you do want shown (or you want to promote a brand-new library before user search volume catches up), add a row in admin and tick the **Pinned?** column. The weekly refresh never touches `is_pinned`, so the pin survives every run.
- **Refresh now** — instead of waiting for next Monday's run, hit the "Refresh from Algolia" button on the admin changelist to trigger a refresh on demand. Useful after editing the exclusion list or adding a pin.

## Failure modes

The homepage keyword badge row is designed to fail closed, not open:

- **LLM is down or returns nonsense.** The refresh skips the database write entirely. The previous week's keyword badges stay on the homepage. Unfiltered Algolia output is never displayed.
- **Algolia is down.** Same outcome — the refresh aborts, last week's keyword badges stay.
- **No releases are flagged as live.** The refresh logs and exits without touching the database.
- **Database table is empty (e.g., right after deploy).** The template hides the keyword badge row cleanly rather than rendering an empty placeholder.

Once a term has been written to the database, it stays there until an admin removes it — even if Algolia stops returning it. That's intentional: a term that was popular and admin-approved last month is probably still relevant this month. Admins can spot stale rows by sorting by the "updated at" timestamp.

Each weekly refresh **demotes** rows it didn't surface this run — their `rank` gets bumped past the live top-N so they sort below the fresh rows on the homepage. Demotion is additive: a row stale for one week sits just below the live block, a row stale for many weeks sinks further. Pinned rows (rows with **Pinned?** ticked) are exempt and keep their curator-set rank.

## Schedule

Refreshes run weekly on Mondays at 05:15 UTC. Each run looks back two weeks of Algolia analytics.

## Required external services

- **Algolia Analytics API** — provides the raw top-searches list. Credentials are already configured for the release-report wordcloud feature.
- **OpenRouter (via the OpenAI SDK)** — runs the LLM quality check. Credentials are already configured for the news summarizer.
