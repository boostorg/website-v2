# Boostlook.CSS Pipeline

A relationship diagram mapping the Boostlook.CSS pipeline end to end: sources, dependencies, transformations, and outputs.

---

## Pipeline Overview

```
+------------------------------------------------------------------------------------+
│                              SOURCE REPOSITORIES                                   |
│                                                                                    │
│  boostorg/boostlook           boostorg/website-v2-docs    boostorg/website-v2      │
│  |-- boostlook.css            |-- documentation content   |-- Django app           │
│  +-- font assets              +-- (S3 archive)            |-- templates            │
│       (Noto Sans, Monaspace)                              |-- static/css/          │
│                                                           │   +-- boostlook.css    │
│                                                           +-- core/                │
│                                                               |-- views.py         │
│                                                               |-- htmlhelper.py    │
│                                                               +-- constants.py     │
+------------------------------------------------------------------------------------+
        │                               │                            │
        │ deploy-website.sh             │                            │
        │ (merge develop -> master)     │                            │
        v                               v                            v
+--------------+   5-min wait   +-----------------+            +--------------+
│  boostlook   │--------------->│ website-v2-docs │----------->│  website-v2  │
│  CI/CD       │   for GHA      │ CI/CD           │            │  CI/CD       │
+--------------+                +-----------------+            +--------------+
```

---

## CSS File Relationships

```
static/css/boostlook.css (vanilla CSS, from boostorg/boostlook repo)
│
|-- Root Variables -------- Light/dark theme tokens (colors, spacing, fonts)
|-- Font-Face ------------ Noto Sans, Monaspace Neon/Xenon
│                          Sources (fallback chain):
│                            1. ../font/*.ttf (local dev)
│                            2. /static/font/*.woff2 (deployed/production)
│                            3. ../../../../tools/boostlook/*.woff2 (local boostlook repo)
│                            4. https://cppalliance.org/fonts/*.ttf (CDN fallback)
|-- CSS Reset
|-- Global .boostlook ---- Cross-template base styles
|-- AsciiDoctor styles --- .boostlook content sections
|-- Antora styles -------- .source-docs-antora / article.doc
|-- Quickbook styles ----- .boostlook:not(:has(.doc)) selectors
+-- README styles -------- section#libraryReadMe

Supporting CSS files:
|-- static/css/preprocessing_fixes.css -- Frameset layout overrides
|-- static/css/styles.css --------------- Site-wide Tailwind (built from frontend/)
|-- static/css/docsstyles.css ----------- Docs Tailwind (docstailwind.config.js)
+-- static/css/userguidestyles.css ------ User guide Tailwind (userguidetailwind.config.js)
```

---

## Template Integration

```
templates/base.html
│
|-- <link href="{% static 'css/boostlook.css' %}" rel="stylesheet">
│   +-- Loaded globally on every page
│
|-- templates/original_docs.html ---- Wrapper for legacy docs
│   +-- Renders modernized content with .boostlook class
│
|-- templates/docsiframe.html ------- Wrapper for fully modernized (Antora) docs
│   +-- Renders content with .source-docs-antora class
│
|-- templates/docs_libs_placeholder.html -- Preload hint for boostlook.css
│
|-- templates/libraries/detail.html -- Library detail page
│   +-- <section class="boostlook"> wrapping README content
│
+-- templates/versions/detail.html --- Version/release page
    +-- <section class="boostlook"> wrapping release notes
```

---

## Documentation Rendering Pipeline

This is the core decision tree in `ModernizedDocsView` (`core/views.py`). When a user visits a documentation URL (e.g., `/doc/libs/1_87_0/libs/filesystem/index.html`):

```
                        Incoming request
                              │
                              v
                    +-- Check RenderedContent -+
                    │   database cache         │
                    │   (core/models.py)       │
                    +--------------------------+
                   Cache hit │           │ Cache miss
                             │           │
                             v           v
                   Return cached    Fetch from S3
                   HTML             (core/boostrenderer.py)
                                         │
                                         v
                              Parse HTML with BeautifulSoup
                                         │
                                         v
                    +----------------------------------------+
                    │  Which processing path? (constants.py) │
                    +----------------------------------------+
                             │
          +------------------┼-------------------------------------+
          │                  │                  │                  │
          v                  v                  v                  v
   NO_PROCESS_LIBS   FULLY_MODERNIZED   NO_WRAPPER_LIBS    Standard
   (8 libraries)     _LIB_VERSIONS      (25+ libraries)   (everything
                     (charconv, redis,                      else)
                      url, tools/)
          │                  │                  │                  │
          v                  v                  v                  v
   Pass-through       _fully_modernize   Header only,      Full legacy
   Minimal changes    _content()         no body wrapper    modernization
   (canonical link,     │                  │                │
    required tags)      │                  │                │
                        │                  │                │
                        v                  │                │
              +-- Antora path? --+         │                │
              │                  │         │                │
              v                  v         │                │
      source-docs-     AsciiDoc path       │                │
      antora class     (currently          │                │
      docsiframe.html  unused, kept        │                │
                       for possible        │                │
                       reactivation)       │                │
                                           │                │
                                           v                v
                                  +--  modernize_legacy_page() --------+
                                  │    (core/htmlhelper.py)            │
                                  │                                    │
                                  │  1. Remove CSS classes             │
                                  │  2. convert_name_to_id()           │
                                  │  3. remove_library_boostlook()     │
                                  │     (strip per-lib boostlook.css   │
                                  │      links, use site-wide instead) │
                                  │  4. remove_embedded_boostlook()    │
                                  │     (strip inline <style> with     │
                                  │      .boostlook selectors)         │
                                  │  5. Inject modern <head>           │
                                  │  6. Wrap body with .boostlook class│
                                  │  7. Rewrite boost.org -> local URLs│
                                  +------------------------------------+
                                                 │
                                                 v
                                        original_docs.html
                                        template renders
                                                 │
                                                 v
                                  Store in RenderedContent cache
                                                 │
                                                 v
                                  Return HTML with cache headers
```

---

## CSS Class Application by Documentation Type

| Documentation Type | CSS Classes Applied | Selector Target in boostlook.css | Processing Function | Example Libraries |
|---|---|---|---|---|
| **Legacy HTML / Quickbook** | `.boostlook` | `.boostlook:not(:has(.doc))` | `modernize_legacy_page()` | accumulators, iterator, spirit |
| **Antora (modern)** | `.boostlook`, `.source-docs-antora` | `div.source-docs-antora.boostlook`, `article.doc` | `modernize_legacy_page()` with `SourceDocType.ANTORA` | charconv (1.87+), redis (1.89+), url |
| **AsciiDoc files** | `.boostlook` | `.boostlook` (general) | `convert_adoc_to_html()` via Asciidoctor | Library READMEs in `.adoc` format |
| **Markdown files** | `.boostlook` | `section#libraryReadMe` | `process_md()` via Mistletoe | Library READMEs in `.md` format |
| **Frameset (preprocessor)** | `.boostlook` | `.boostlook` + `preprocessing_fixes.css` | `modernize_preprocessor_docs()` | preprocessor (older versions) |
| **No-wrapper libs** | No `.boostlook` wrapper | Inherits base styles only | Header injection, no body wrap | array, assert, describe, mp11, etc. |
| **No-process libs** | None | None (pass-through) | Minimal: canonical link only | filesystem, gil, hana, locale, etc. |

---

## Library Classification (core/constants.py)

Three lists control which processing path a library takes:

```
+---------------------------------------------------------------+
│ NO_PROCESS_LIBS (8 libraries)                                 │
│ Docs served as-is from S3, no boostlook styling               │
│                                                               │
│ filesystem, gil, hana, locale, iostreams, preprocessor,       │
│ serialization, wave                                           │
+---------------------------------------------------------------+

+---------------------------------------------------------------+
│ NO_WRAPPER_LIBS (25+ libraries)                               │
│ Get a site header but no .boostlook body wrapper              │
│                                                               │
│ array, assert, bloom, charconv, cobalt, compat,               │
│ container_hash, describe, endian, exception, hash2, io,       │
│ lambda2, leaf, mp11, predef, process (libs/ and doc/html/),   │
│ property_map_parallel, qvm, redis, smart_ptr, system,         │
│ throw_exception, unordered, uuid, variant2                    │
+---------------------------------------------------------------+

+---------------------------------------------------------------+
│ FULLY_MODERNIZED_LIB_VERSIONS (version-specific)              │
│ Use Antora/modern rendering with source-docs-antora class     │
│                                                               │
│ charconv (1.87, 1.88, 1.89, latest, develop, master),         │
│ redis (1.89, latest, develop, master),                        │
│ url (doc/antora/url), tools/ (all versions)                   │
│                                                               │
│ Note: versions are explicitly enumerated, not range-matched.  │
│ New versions must be added to the list manually.              │
+---------------------------------------------------------------+

+---------------------------------------------------------------+
│ Everything else (~150 libraries)                              │
│ Full legacy modernization with .boostlook wrapper             │
+---------------------------------------------------------------+
```

---

## Deployment Pipeline

The deploy script (`scripts/deploy-website.sh`) orchestrates deployment of all three repos in a specific order:

```
Step 1: boostorg/boostlook
   │  git merge develop -> master (ff-only)
   │  git push to master
   │
   │  -- 5 minute wait --
   │  Pushing master triggers GitHub Actions defined
   │  in the boostorg/boostlook repo itself (repository_dispatch
   |  and workflow_dispatch events targeting website-v2-docs
   |  and website-v2).
   │
   │  In website-v2, the CI-GCP workflow
   │  (actions-gcp.yaml) fires on master push:
   │    - Builds a new Docker image
   │    - Deploys to GKE (production namespace)
   │  This workflow includes a step that installs
   │  boostlook.css into the Docker image, so the
   │  new CSS is picked up automatically.
   │
   v
Step 2: boostorg/website-v2-docs
   │  git merge develop -> master (ff-only)
   │  git push
   │
   v
Step 3: boostorg/website-v2
      git merge develop -> master (ff-only)
      git push to master
      -> triggers CI-GCP workflow (actions-gcp.yaml)
        which builds and deploys to GKE production
```

**Why the 5-minute wait after boostlook?** Pushing to `boostorg/boostlook` master triggers GitHub Actions (defined in the boostlook repo) that propagate the updated CSS to downstream repos. The wait ensures those Actions complete before the next repos are deployed, preventing a deployment uses stale CSS. The specific workflows triggered are configured in the `boostorg/boostlook` repository's `.github/workflows/` directory. It may be worth trying to automate observing the github actions and moving on once they've succeeded, rather than this somewhat arbitrary wait.

---

## Non-Obvious Relationships

1. **boostlook.css is committed, not built.** Unlike the Tailwind-based site CSS (`styles.css`, `docsstyles.css`) which are compiled from source, `boostlook.css` is hand-authored vanilla CSS maintained in the separate `boostorg/boostlook` repo and copied into `static/css/`.

2. **Per-library boostlook links are stripped.** Some library docs ship with their own `<link>` to `boostlook.css`. The `remove_library_boostlook()` function strips these so the site-wide version is used instead, ensuring consistency.

3. **Embedded boostlook styles are also stripped.** `remove_embedded_boostlook()` removes any `<style>` blocks containing `.boostlook` selectors, again to enforce the site-wide version.

4. **A library can appear in multiple lists.** For example, `charconv` is in `NO_WRAPPER_LIBS` (gets a header but no wrapper) AND in `FULLY_MODERNIZED_LIB_VERSIONS` (uses Antora rendering). The fully-modernized check takes precedence when both match.

5. **Antora detection is partially path-based.** `establish_source_content_type()` falls back to checking if "antora" appears in the URL path when the S3 metadata doesn't specify a content type.

6. **Font fallback chain spans four sources.** Fonts cascade from local project files, to deployed static files, to the boostlook repo path, to the cppalliance.org CDN. This handles both local development and production scenarios.

7. **`static_deploy/css/boostlook.css` is a deploy-time copy.** The canonical file is `static/css/boostlook.css`; the `static_deploy/` version is generated during the Django `collectstatic` step.

---

## Key Files Reference

| File                                 | Role in Pipeline                                                                                    |
|--------------------------------------|-----------------------------------------------------------------------------------------------------|
| `static/css/boostlook.css`           | Core CSS framework (vanilla CSS)                                                                    |
| `static/css/preprocessing_fixes.css` | Frameset layout overrides                                                                           |
| `core/constants.py`                  | Library classification lists (`NO_PROCESS_LIBS`, `NO_WRAPPER_LIBS`, `FULLY_MODERNIZED_LIB_VERSIONS`) |
| `core/htmlhelper.py`                 | HTML transformation functions (`modernize_legacy_page()`, `remove_library_boostlook()`, etc.)       |
| `core/views.py`                      | `ModernizedDocsView` rendering decision tree                                                        |
| `core/boostrenderer.py`              | S3 content fetching (`get_content_from_s3()`, `get_s3_keys()`)                                      |
| `core/models.py`                     | `RenderedContent` database cache model                                                              |
| `core/asciidoc.py`                   | AsciiDoc to HTML conversion via Asciidoctor                                                         |
| `templates/base.html`                | Global `<link>` to boostlook.css                                                                    |
| `templates/original_docs.html`       | Legacy docs wrapper template                                                                        |
| `templates/docsiframe.html`          | Fully modernized docs wrapper template                                                              |
| `templates/libraries/detail.html`    | Library page (applies `.boostlook` to README section)                                               |
| `templates/versions/detail.html`     | Version page (applies `.boostlook` to release notes)                                                |
| `scripts/deploy-website.sh`          | Three-repo deploy orchestration with boostlook-first ordering                                       |
