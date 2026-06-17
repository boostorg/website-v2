# Library Sub-page Data Extraction — Findings & Proposed Maintainer Format

> Findings from the library sub-page data-extraction spike. Proposed maintainer content
> format: [`website-template.adoc`](./website-template.adoc) — worked examples:
> [header-only (Beast)](./boost-beast-website.adoc),
> [separately-compiled library (Filesystem)](./boost-filesystem-website.adoc).

Each Boost release is automatically processed by a pipeline that reads each library's repository (its metadata file, README, docs, commit history, dependencies) and saves it to our database. The sections below sort every
sub-page field by whether that pipeline already captures it.

---

# ✅ Supported fields

These fields map to data we already collect. Next step is simply to connect the
sub-page card to the real data and remove the placeholder mock-up.

## Group A — Basic metadata

| Field | What it is | _Dev: backed by_ |
|---|---|---|
| Title / display name | The library's name | `Library.name` |
| Short description | One-line summary | `LibraryVersion.description` |
| Category tags | Topic labels (e.g. "Networking") | `Library.categories` |
| C++ standard tag | Minimum C++ version required | `LibraryVersion.cpp_standard_minimum` |
| "Added in" version | Boost release it first appeared in | `Library.first_boost_version` |

_Dev: all sourced from each repo's `meta/libraries.json` at release tag._
Example `libraries.json` for Boost.Beast: https://github.com/boostorg/beast/blob/develop/meta/libraries.json

## Group B — Button Links

| Field | What it is | _Dev: backed by_ |
|---|---|---|
| Documentation | Link to the library's docs on Boost site | internal doc link (e.g. `/doc/libs/1_90_0/doc/html/accumulators.html`) |
| Source code | Link to the library's repository at the release tag | GitHub link (e.g. `https://github.com/boostorg/accumulators/tree/boost-1.90.0`) |
| Discuss in Slack | Link to the Boost Slack | static link to `https://cpplang.slack.com` |
| GitHub Issue | Link to the repository's issues | GitHub Issue link (e.g. `https://github.com/boostorg/accumulators/issues`) |

> _Dev — entry point:_ `_build_quick_start_links(documentation_url, github_url,
> github_issues_url)` (`libraries/views.py:56`), assembled in `get_v3_context_data`
> (`views.py:521+`). Slack is set separately — `slack_url = SLACK_URL` (`views.py:533`).

## Group C — Dependencies & Contributors
*Who built it and what it connects to.*

| Field | What it is | _Dev: backed by_ |
|---|---|---|
| Dependencies card | Other Boost libraries this one needs | `LibraryVersion.dependencies` (dependency artifact) |
| Contributors | Authors for this release + all-time | commit history + authors/maintainers |

> _Dev — entry point:_ `update_library_version_dependencies` (`libraries/github.py:635`)
> ingests the CI `boost-dep-artifact` into the `LibraryVersion.dependencies` M2M (not from
> `libraries.json`) — runs as a **daily Celery task** (`config/celery.py:77`, 8:05 AM), not
> the release pipeline; rendered via `_build_dependencies_list(...)` (`views.py:68`).

> _Dev — entry point:_ `ContributorMixin.get_context_data` (`libraries/mixins.py:146`)
> assembles authors/maintainers (from `libraries.json`) + contributors (from git commit
> history); rendered in `get_v3_context_data` (`views.py:568–593`).

## Group D — Long-form & related content
*The fuller written material.*

| Field | What it is | _Dev: backed by_ |
|---|---|---|
| Documentation (long-form body) | The library's full write-up | rendered HTML from `doc/library-detail.adoc` / README (`RenderedContent`) |
| Latest posts | Recent blog/news mentions | `get_latest_post_cards` |

> _Dev — entry point:_ `Library.get_description(client, tag)` (`libraries/models.py:371`)
> resolves the long-form HTML lazily at request time (cache → `RenderedContent` → live
> GitHub fetch of `doc/library-detail.adoc`/`README.md`); set on the view at `views.py:514`.

> _Dev — entry point:_ `get_latest_post_cards(limit=3)` (`news/services.py:83`, called at
> `views.py:566`) — site-wide latest posts, not library-specific.

---

# ❌ Not supported fields

No source in the current pipeline produces these. They're grouped by **how we'd fill the gap**.

## Group E — Maintainer-provided content *(needs a new repo file)*
*Technical content that should live with the code and change with each release. Best owned by each library's maintainers.*

| Field | What it is |
|---|---|
| "About" blurb & code example | Marketing intro + a representative code snippet |
| "Library is designed for…" copy | Short sectioned explanation of what it's for |
| "Edit in Compiler Explorer" | Opens the example on godbolt.org — needs the maintainer's code to build the URL |
| Install — for separately-compiled libraries only | The 10 separately-compiled libraries declare `:separately-compiled-library: true` and author the extra build/link steps. **Everything else is header-only by default and authors nothing** — the site renders a generic "get Boost" card. |
| Benchmarks | Performance numbers, shown as a bar chart |

> _The 10 separately-compiled libraries_ (the only Boost libraries that must be built separately — all set
> `:separately-compiled-library: true` and author an `[#install]` section): **Filesystem, IOStreams,
> ProgramOptions, Python, Regex, Serialization, Signals, System, Thread, Wave.**

**Recommendation:** add one **optional** file to each library's repository, read
automatically at each release (just like the existing metadata file). If a library
doesn't provide it, the UI layout will handle the empty state. 

## Group F — Link-only
*These are links out that we can determine by logic pattern.*

| Field | Where it points |
|---|---|
| Quick Start common use case | Boost documentation page – Rob to align internally to confirm first |
| Quick Start code example | Boost documentation page (the *card* is a link, not an inline snippet) – ⚠️ confirm with Rob. Note: the maintainer's single example code block still lives in the `.adoc` `[#playground]` section to power the Compiler Explorer button (Group E). |


# Proposed wiring (does not exist yet)

A new ingestion path that mirrors how `meta/libraries.json` is already fetched and parsed per release. 
The proposed format is **AsciiDoc** — see [`website-template.adoc`](./website-template.adoc) and the worked examples ([Beast](./boost-beast-website.adoc), [Filesystem](./boost-filesystem-website.adoc)) — chosen because Boost docs are already authored in AsciiDoc, so maintainers stay in a familiar format and extraction keys off stable section IDs.

1. **Source file** — maintainers add an **optional** `meta/website.adoc` to their repo,
   committed alongside the code so it versions with each release tag.
2. **Fetch** — new `get_website_adoc()` in `core/githubhelper.py`, sibling to the existing
   `get_libraries_json()` (`~:616`); same `GithubAPIClient` file-fetch at the release tag.
3. **Parse** — new `parse_website_adoc()` mirroring `parse_libraries_json()`: render/parse
   the AsciiDoc and extract content by its **stable section IDs** (`[#about]`,
   `[#designed-for]`, `[#playground]`, `[#install]`, `[#benchmarks]`) and document attributes
   (`:designed-for:`, `:separately-compiled-library:`), normalizing into a dict. `:separately-compiled-library:`
   **defaults to `false`** when absent — `[#install]` is only expected for separately-compiled libraries.
4. **Store** — new `LibraryVersion.website_data` JSONField, mirroring the existing raw
   `data` field. 
5. **Ingest step** — call the fetch/parse inside `versions/tasks.py:import_library_versions`
   (the per-release step that already pulls `libraries.json`), saving onto `website_data`.
6. **Render** — the view reads `LibraryVersion.website_data` and renders each card/section as
   it does for the existing fields. Install is special: render the **website-owned generic
   install card for every library** (reuse the existing `_install_card.html`, already used on
   homepage/community/examples), and append the maintainer's `[#install]` build steps only
   when `:separately-compiled-library: true`.

**Field → `website.adoc` section:**

| Field | AsciiDoc source | Render path |
|---|---|---|
| "About" blurb & code example | `[#about]` section + its `[source]` block | `_code_block_card.html` (existing syntax highlighting) |
| "Library is designed for…" | `[#designed-for]` sections | AsciiDoc → HTML |
| "Edit in Compiler Explorer" | **derived from the `[#playground]` code** — the maintainer provides a single code block whose only job is to feed this button (the Quick Start example *card* itself is a link, see Group F) | URL-encode the snippet into a `godbolt.org` link at render time — no extra stored data |
| Install | `:separately-compiled-library:` attribute (default `false`) + optional `[#install]` build steps (separately-compiled libraries only) | **generic install card is website-owned** (reuses existing `_install_card.html`) for every library; the maintainer's `[#install]` build steps are appended only when `:separately-compiled-library: true` |
| Benchmarks | `[#benchmarks]` sub-sections (each a bar table + axis attributes) | bar chart |

# Format decision: AsciiDoc vs JSON

Chose **AsciiDoc**. It's not unconditional — the right format depends on the content mix:

- **AsciiDoc wins** on **adoption** (Boost libraries already author `doc/*.adoc`, and adoption
  is the #1 risk) and on **code examples** (a natural `[source]` block vs. an unreviewable
  escaped-`\n` string in JSON). It also degrades gracefully — a missing section just yields
  an empty state, matching the "optional, best-effort" intent.
- **JSON would win** on **parsing reliability** (`json.load` vs. extract-by-section-ID),
  **validation** (JSON Schema), and **structured data** (benchmarks are tabular).

This file is mostly prose + code, and adoption is the binding constraint, so AsciiDoc is the
call. The one structured field (benchmarks) is the weak spot — brittle extraction, no schema
validation. If structured fields grow, reconsider JSON.

---

# Appendix — Pipeline overview

*Technical reference: how the existing release pipeline ingests and stores library data.*

Each Boost release is processed by ~14 sequential import steps, orchestrated by
`ReleaseTasksManager` (`libraries/management/commands/release_tasks.py`). The content it
captures comes from these sources:

| Source | What it provides | _Dev: code_ |
|---|---|---|
| `boostorg/boost` `.gitmodules` @ tag | list of library submodules | `core/githubhelper.py:get_gitmodules`, `versions/tasks.py:import_library_versions` |
| each repo `meta/libraries.json` @ tag | **canonical metadata** (name, key, authors, one-line description, category, maintainers, cxxstd/cxxstd_max, modules) | `get_libraries_json` → `parse_libraries_json` |
| GitHub API | repo info, tags/releases, issues, PRs, commits, avatars | `core/githubhelper.py` (`GithubAPIClient`) |
| git clone (bare) | commit stats (insertions/deletions/files changed) | `libraries/github.py:get_commit_data_for_repo_versions` |
| CI artifact `boost-dep-artifact` | per-version dependency graph | `libraries/github.py:update_library_version_dependencies` † |
| S3 compiled docs | `documentation_url`, release-notes HTML | `libraries/tasks.py`, `versions/releases.py` † |
| repo `doc/library-detail.adoc` (or `README.md`) | long-form HTML, cached | `Library.get_description` → `RenderedContent` ‡ |

> † Refreshed by **separate daily Celery Beat tasks** (`config/celery.py`), not the
> release-pipeline steps above — e.g. `update_library_version_dependencies` runs at 8:05 AM.
> ‡ Resolved **lazily at request time** (cache → `RenderedContent` → live GitHub fetch),
> not pushed by the batch pipeline at all.

**Where it's stored** (`libraries/models.py`):

| Model | Holds |
|---|---|
| `Library` | name, key, slug, description, github_url, graphic, tier (FLAGSHIP/CORE/…), categories (M2M), authors (M2M), raw `data` (JSON) |
| `LibraryVersion` | per-release description, documentation_url, cpp_standard_min/max, cpp20_module_support, dependencies (M2M), commit stats, raw `data` (JSON) |
| `Commit` / `CommitAuthor` / `CommitAuthorEmail` | contributor history |
| `Issue` / `PullRequest` | GitHub activity |
| `RenderedContent` | rendered long-form HTML cache (README / `library-detail.adoc`) |
