# AI-Assisted Description for Blog & News — Research Findings

> Prepared for handoff to Windsurf to build an implementation plan.
> Scope: add a plain-text **Description** field to Blog (and News) posts on the
> v3 create-post page (`/v3/news/add/`), extend the existing AI summarization to
> populate it, add an "Auto-Generate Description" button with state handling, and
> a localStorage auto-save indicator (Saving / Saved).
> Source issue: "AI-assisted desc — blog & news". Figma file `5j0fQssrV9ipoU16P7hfKy`.

---

## 0. TL;DR for the planner

- The page at **`/v3/news/add/`** is served by **`V3AllTypesCreateView`** →
  template **`templates/news/v3/create.html`**. (config/urls.py:273)
- The frontend **IS reactive**: it uses **Alpine.js** (`alpinejs ^3.10.2`) plus a
  **TipTap** WYSIWYG editor. localStorage auto-save is very achievable here.
- An **AI summarization pipeline already exists** in `news/tasks.py`. It already
  does exactly the per-type input routing the issue asks for (blog/news → body
  `content`; link/video → fetch the URL). The main change is the **prompt cap
  (256 → 1000 chars)**, exposing it via an **on-demand endpoint**, and wiring the
  button/field in the UI.
- The model already has an **`Entry.summary`** TextField used as the post's
  description on cards/detail. **Biggest open decision: reuse `summary` as the
  "Description" vs. add a new `description` field.** See §6.
- Figma confirms the **redundant Description** the team flagged: the design shows
  an "Auto-Generate Description" button + Saving indicator under **both** the
  Content field and the Description field. Per direction: **keep ONE** — on the
  Description field only.

---

## 1. Where posts are defined (Task 1)

### `news/models.py`
Concrete-base inheritance. `Entry` is a real table; each subtype has its own table + 1:1.

- **`Entry`** (base, news/models.py:59) — shared fields:
  - `title` (CharField 255), `content` (TextField, blank) — the body,
    `external_url` (URLField), `image`, `publish_at`, `author`, `moderator`, …
  - **`summary`** (TextField, blank) — help text: *"AI generated summary. Delete to
    regenerate."* (news/models.py:94) — **this is the existing AI description field.**
  - `Entry.save()` (news/models.py:217) auto-dispatches summary generation:
    ```python
    if not self.summary:
        summary_dispatcher.delay(self.pk)   # background Celery task
    ```
  - `use_summary` / `visible_content` (news/models.py:205-215) and
    `EntryDetailView._post_card_item` (news/views.py:286) use `summary` as the
    **displayed description** on post cards & detail pages.
- **`News(Entry)`** (news/models.py:248) — adds `attachment` (FileField).
- **`BlogPost(Entry)`** (news/models.py:266) — adds **`abstract`** (CharField 256).
  Note: `abstract` is **not** used by the v3 forms/templates — looks legacy. Do not
  confuse it with the new Description. Confirm before reusing.
- `Link`, `Video`, `Poll` also subclass `Entry`.
- `NEWS_MODELS = [BlogPost, Link, News, Poll, Video]`.

### `news/forms.py`
ModelForms; **none currently expose `summary`/`description`.**
- `BlogPostForm` / `NewsForm`: `fields = ["title", "publish_at", "content", "image"]`
- `LinkForm` / `VideoForm`: `fields = ["title", "publish_at", "external_url", "image"]`
- `EntryForm.save()` auto-approves entries that don't need moderation.

### `news/views.py` + routing
- **`/v3/news/add/` → `V3AllTypesCreateView`** (config/urls.py:273, view at
  news/views.py:487). It's a multiplexer:
  - `_POST_TYPE_MAP = {"blog": (BlogPost, BlogPostForm), "news": (News, NewsForm),
    "link": (Link, LinkForm), "video": (Video, VideoForm)}`
  - `post()` (news/views.py:510) reads `post_type` from POST, picks the
    model+form, validates, saves, emails moderators, redirects.
  - `_v3_create_context()` (news/views.py:358) supplies `post_type_options`
    (blog/news/video/link), `related_libraries_options`, `publish_at_initial`.
- Gated by the **`v3` waffle flag** via `V3Mixin` (core/mixins.py). Non-v3 falls
  back to legacy `AllTypesCreateView` (`news/create.html`).
- Legacy per-type create/update views also exist (`BlogPostCreateView`, etc.) and
  `EntryUpdateView` (news/views.py:583) for editing — **don't forget the edit path**
  if Description must be editable after creation.

---

## 2. Existing GenAI / summarization usage (Task 2)

**This is the feature to extend.** Located in **`news/tasks.py`** (Celery tasks).

- **`summarize_content(content, title, model)`** (news/tasks.py:15) — the LLM call:
  - Client: `OpenAI(base_url=OPENROUTER_URL, api_key=OPENROUTER_API_KEY)` — i.e.
    **OpenRouter** via the OpenAI SDK. Settings: `config/settings` →
    `OPENROUTER_API_KEY`, `OPENROUTER_URL`.
  - Model passed in is **`"gpt-oss-120b"`**.
  - **System prompt hard-codes `max_length = 256`** characters and instructs the
    model to keep the summary under that. ⭐ **This is the prompt to update to 1000.**
  - Prompt is already hardened (plain text only, no markdown, impersonal voice,
    NSFW/security guardrails) — keep those when bumping the limit.
- **`summary_dispatcher(pk)`** (news/tasks.py:79) — routes by type, **already
  matching the issue's Input rule**:
  ```python
  {"news": set_summary_for_event_entry,      # uses entry.content
   "blogpost": set_summary_for_event_entry,  # uses entry.content
   "link": set_summary_for_link_entry,       # fetches entry.external_url
   "video": set_summary_for_video_entry,     # not implemented
   "poll":  set_summary_for_poll_entry}      # not implemented
  ```
- `set_summary_for_event_entry` (news/tasks.py:96) — blog/news; **skips if
  `len(content) < CONTENT_SUMMARIZATION_THRESHOLD` (1000, news/constants.py:3).**
- `set_summary_for_link_entry` (news/tasks.py:112) — fetches the URL (`requests`),
  `extract_content(markup)` (news/helpers.py), then summarizes.
- `set_summary_for_video_entry` / `set_summary_for_poll_entry` — stubs ("not implemented").
- `save_entry_summary_value(summary, pk)` (news/tasks.py:70) — writes result to
  `entry.summary` (via Celery `link=` callback).
- Existing tests: `news/tests/test_models.py`; management command
  `news/management/commands/backpopulate_summaries.py`.

**Current trigger model:** generation is **automatic & asynchronous** — fired from
`Entry.save()` whenever `summary` is empty. The new feature wants a **user-triggered,
one-time, synchronous-feeling** button. These need reconciling (see §6).

---

## 3. The v3 create-post frontend

### `templates/news/v3/create.html`
- Alpine component **`createPostForm()`** (inline script at bottom). Reactive state:
  `postType`, `errors`, getters `isWriteUp` (blog||news), `isLinkType` (video||link).
- Field visibility is toggled by `:style`/CSS based on post type.
- **Current field wiring (important):**
  - Blog/News (`isWriteUp`): **WYSIWYG editor** via `_wysiwyg_editor.html`,
    `name="content"` (create.html:70).
  - Link/Video (`isLinkType`): a **plain "Description" textarea** via
    `_field_textarea.html`, **but bound to `name="content"`**, `field_id="description"`
    (create.html:75-77). → i.e. the link "Description" is actually saved to the
    model's `content` field. **This is the "existing experience on link post types"**
    the issue references.
  - `prepareSubmit` (create.html:117) does client-side validation; chooses
    `#field-content` vs `#field-description` based on type.
- **No description/summary-specific field, no Auto-Generate button, and no
  auto-save exist yet.** They must be added.

### Reusable field includes (templates/v3/includes/)
- `_field_textarea.html` — plain textarea; supports `name`, `field_id`, `label`,
  `value`, `alpine_error`, `alpine_disabled_expr`, etc. **Use this for Description.**
- `_field_text.html`, `_field_dropdown.html`, `_field_datetime.html`,
  `_field_file.html` — other field types already used on the page.
- `_wysiwyg_editor.html` — TipTap mount point (`data-wysiwyg="v3"`).
- `templates/includes/icon.html` — central pixel-art (pixelarticons) icon set.
  **No "save"/"spinner" icon yet** — add the two Figma icons here (paths in §5).

### WYSIWYG editor + build
- Source: **`frontend/wysiwyg-editor.js`** (TipTap, marked, turndown, DOMPurify, …).
- Built with esbuild → **`static/js/v3/wysiwyg-editor.js`**:
  ```
  npm run build:wysiwyg   # esbuild frontend/wysiwyg-editor.js --bundle --minify ... --external:mermaid
  ```
  ⭐ **Edit `frontend/…` then rebuild — never hand-edit the bundled `static/js/v3/…`.**
- CSS: per-component files in `static/css/v3/` (Tailwind built via `npm run build`).
  The page loads **`static/css/v3/create-post-page.css`** (create.html:8) — add
  Description/button/indicator styles here (or a new component CSS).
- Alpine.js is bundled site-wide (see `templates/base.html`). localStorage is already
  used there for theme/login — same pattern works for auto-save.

---

## 4. Figma design findings (Task 3)

**Primary frame:** `node-id=7134-42434` — *"Unfilled Post, Desktop, Light"* (the
create-post page for this feature). **Saving/Saved icon states:** `node-id=6635-24462`.

### Field order in the design (top → bottom)
1. **Post type*** (dropdown, e.g. "Blog")
2. **Post title*** ("Title")
3. **Content*** — textarea, placeholder "What would you like to write?",
   char counter top-right **"20,000 left"**
   - action row: **[Auto-Generate Description]** button (left) + **Saving** indicator (right)  ← redundant, see note
4. **Description** — textarea, placeholder "What would you like to write?",
   char counter top-right **"1,000 left"** ⭐ (confirms the 1000-char max)
   - hidden helper text "Fetched automatically" (shown for link/video, where the
     description is derived from the URL)
   - action row: **[Auto-Generate Description]** button (left) + **Saving** indicator (right)
5. **Image** — "Choose File", help "This should be a PNG or JPEG format and no longer than 5MB"
6. **Related Libraries** (dropdown "Select")
7. **Publish Date** ("Today at 10:00AM")
8. **Cancel** / **Submit** buttons

### ⚠️ The redundancy (confirmed)
The design shows the **Auto-Generate Description button + Saving indicator twice** —
once under **Content** and once under **Description**. Per direction:
**implement only ONE** — attach the button + Saving/Saved indicator to the
**Description** field. (Auto-generating the *body* makes no sense; the Content field
should not carry the "Auto-Generate Description" control.)

### Description field — exact spec (node 7134:42463)
- Label **"Description"** (12px, medium, `#050816`), counter **"1,000 left"**
  right-aligned, same style.
- Field: white surface `--surface/weak #ffffff`; border `--stroke/weak rgba(5,8,22,0.1)`,
  1px solid; radius **12px** (`--xl`); padding **16px** horizontal / **13px** vertical.
- Placeholder text `#585a64` (`--text/secondary`), 14px regular.
- Plain textarea — **no rich text.**

### "Auto-Generate Description" button (node 7134:42477 → component 55:175)
- Outlined style: border `--stroke/strong rgba(5,8,22,0.25)`, 1px solid;
  radius **8px** (`--l`); padding **8px**; min-width **128px**.
- Label "Auto-Generate Description", 14px medium, `#050816`.
- Maps to the project's existing secondary/outline button styling (see
  `static/css/v3/buttons.css` / `.btn-secondary`).

### Saving / Saved indicator (node 7134:42478 and 6635:24462)
- Right-aligned in the action row; `display:flex; gap:8px; align-items:center`.
- Text 12px medium, **`#71737b`** (`--text/tertiary`); icon **16px**, same color.
- **"Saving"** label + **spinner icon** (pixel-art loading burst). SVG path
  (viewBox `0 0 13.3333 13.3333`, fill `#71737B`):
  ```
  M7.33333 0H6V4H7.33333V0ZM7.33333 9.33333H6V13.3333H7.33333V9.33333ZM13.3333 6V7.33333H9.33333V6H13.3333ZM4 7.33333V6H0V7.33333H4ZM8.66667 3.33333H10V4.66667H8.66667V3.33333ZM11.3333 2H10V3.33333H11.3333V2ZM4.66667 3.33333H3.33333V4.66667H4.66667V3.33333ZM2 2H3.33333V3.33333H2V2ZM8.66667 10H10V11.3333H11.3333V10H10V8.66667H8.66667V10ZM3.33333 10V8.66667H4.66667V10H3.33333ZM3.33333 10V11.3333H2V10H3.33333Z
  ```
  (Consider animating it with a CSS `rotate` spin while saving.)
- **"Saved"** label + **floppy-disk / save icon**. SVG path
  (viewBox `0 0 13.3333 13.3333`, fill `#71737B`):
  ```
  M1.33333 0H10.6667V1.33333H1.33333V12H2.66667V8H10.6667V12H12V2.66667H13.3333V13.3333H0V0H1.33333ZM4 12H9.33333V9.33333H4V12ZM12 2.66667H10.6667V1.33333H12V2.66667ZM2.66667 2.66667H8.66667V5.33333H2.66667V2.66667Z
  ```
- Add both to `templates/includes/icon.html` (e.g. `icon_name="saving"`,
  `icon_name="saved"`) to stay consistent with the icon system.

---

## 5. Acceptance-criteria → implementation map

| AC | Where it lands |
|---|---|
| Plain-text Description field below the content editor | New block in `create.html` using `_field_textarea.html`, shown for blog/news (and reused for the existing link/video flow) |
| Plain text only, no rich text | Plain `<textarea>` (not the TipTap editor) |
| Auto-save via localStorage + "Saved" indicator | Alpine watchers writing to localStorage (debounced) → toggle Saving/Saved indicator; restore draft on load; clear on submit |
| Generated/entered description saved to DB on submit | Add `summary`/`description` to the relevant ModelForm `fields` so it persists |
| Extend AI function to blog & news | Already routed in `summary_dispatcher`; expose via on-demand endpoint |
| Input = body for blog/news, link for link/video | Already implemented by `set_summary_for_event_entry` vs `set_summary_for_link_entry` |
| Prompt capped at **1000 chars** | Change `max_length = 256` → `1000` in `summarize_content` (news/tasks.py:22) + update `CONTENT_SUMMARIZATION_THRESHOLD` usage if relevant |
| Output populated into Description field; user-editable; 1000-char max | JS sets textarea value; `maxlength=1000` + live "N left" counter; server-side validation too |
| Button states: Idle "Auto-Generate" → Generating (disabled + message) → Generated (hidden, one-time) | Alpine state machine on the button; generating message: *"Hold on! We are generating a description for your content, it may take a few seconds."* |
| Save last time the button was used; one-time per post; **staff unlimited** | Persist a timestamp/flag on `Entry`; staff bypass (see §6) |

---

## 6. Key design decisions / open questions (for the plan)

1. **⭐ Reuse `Entry.summary` as the "Description", or add a new field?**
   - **Recommendation: reuse `summary`.** It's already AI-generated, already the
     thing shown as the post's description on cards/detail, and the per-type input
     routing already exists. Avoids duplicate data/meaning.
   - Caveats to handle if reusing:
     - `summary` is an unbounded `TextField`; enforce the **1000-char max** in the
       form, the JS counter, and the prompt.
     - Today `summary` **auto-generates in the background on save** (`Entry.save`).
       The new UX is **manual, one-time**. Decide: keep auto-gen as a fallback when
       the user never clicks the button, or disable auto-gen now that it's manual.
   - Alternative: a new `description = TextField(max_length=1000)` separate from
     `summary` — cleaner separation but duplicates the concept and forces a choice
     about which one renders on cards. (Requires a migration either way if adding a field.)
   - `BlogPost.abstract` (CharField 256) appears legacy/unused in v3 — likely **not**
     the right home (blog-only, 256 cap). Confirm with the team before touching.

2. **One-time-per-post + "save last button use" + staff unlimited.**
   - Needs persistence — e.g. `description_generated_at = DateTimeField(null=True)`
     (or a counter) on `Entry`. Button hidden once set; **staff bypass** using the
     existing authority check `news/acl.py::can_approve(user)` (already used for
     moderators/superusers elsewhere).
   - **Nuance:** the create page is a *CreateView* — there is **no `Entry` row yet**
     while drafting. So "one-time during creation" must be tracked **client-side**
     (Alpine/localStorage) until first save; the persisted field governs the
     **edit** view (`EntryUpdateView`). The plan should specify both phases.
   - "@jlchilders11 to add details / staff-unlimited approach" is still open in the
     issue — flag that the exact persistence approach may change.

3. **Generation endpoint: sync vs async.**
   - The "may take a few seconds" copy implies the FE waits for a response.
   - **Recommendation:** add a small **authenticated JSON endpoint** (e.g.
     `POST /v3/news/generate-description/`) that accepts `{post_type, content | external_url}`
     and returns `{description}` by calling the existing summarization logic
     (refactor `summarize_content` so it can run inline, not only via Celery).
     Alternative: kick off the Celery task + poll a status endpoint. Decide based on
     acceptable latency / worker setup. Add **CSRF, login-required, and rate limiting**.
   - The **FE/BE Actions table in the issue is blank** — these two URLs need to be
     defined:
     - *Auto-save description field content* → **localStorage only** per AC; no
       backend endpoint strictly required (DB write happens on submit).
     - *Generate description from body/link* → the new endpoint above.

4. **Which post types show the Description field?**
   - Issue scope = **Blog & News**. But the existing link/video flow already uses a
     "Description" textarea (bound to `content`). Decide whether to (a) add a *true*
     Description for blog/news while leaving link/video as-is, or (b) unify all four
     onto the real Description field. Unifying is cleaner but widens scope.

5. **Auto-save scope.** AC mentions auto-save for the Description field; the Figma
   also shows a Saving indicator under Content. Confirm whether auto-save covers
   Content too or Description only. (Recommend Description only for v1, to match the
   "one Description component" direction.)

---

## 7. Suggested implementation surface (checklist for the plan)

**Backend**
- [ ] `news/tasks.py`: bump prompt cap 256 → 1000 in `summarize_content`; make the
      summarization callable synchronously (refactor out the pure LLM call).
- [ ] Decide field strategy (§6.1). If new field or new timestamp → migration in
      `news/migrations/`.
- [ ] `news/forms.py`: add `summary`/`description` to `BlogPostForm`/`NewsForm`
      `fields` (and link/video forms if unified) so it persists on submit; add
      length validation (≤1000).
- [ ] New view + URL: `generate-description` endpoint (auth, CSRF, rate-limit),
      reusing the dispatcher's content-vs-URL routing.
- [ ] Staff-unlimited / one-time gating via `news/acl.py::can_approve`.
- [ ] Reconcile/possibly gate the auto-generate-on-save in `Entry.save()`.

**Frontend**
- [ ] `templates/news/v3/create.html`: add a single Description block
      (`_field_textarea.html`, plain text, `maxlength=1000`, live "N left" counter)
      below the content editor; remove the redundant second button/indicator.
- [ ] Extend the `createPostForm()` Alpine component:
      - button state machine (idle → generating(disabled + message) → generated(hidden));
      - fetch to the generate endpoint;
      - localStorage auto-save with debounced Saving→Saved indicator; draft restore;
        clear on submit;
      - include Description in `prepareSubmit` validation.
- [ ] `templates/includes/icon.html`: add `saving` (spinner) + `saved` (floppy) icons
      (SVG paths in §4); spin the saving icon via CSS.
- [ ] `static/css/v3/create-post-page.css`: style the field, button, counter, and
      indicator to match Figma (radii 12px/8px, colors `#050816`/`#71737b`,
      strokes `rgba(5,8,22,0.1)`/`(...,0.25)`).
- [ ] Mirror changes on the **edit** path (`EntryUpdateView` / its template) if
      Description must be editable post-creation.

**Tests**
- [ ] Prompt length / output ≤1000; dispatcher routing for blog & news; new endpoint
      (auth, payload, error paths); form persistence; staff-vs-non-staff gating.

---

## 8. Key file reference

| Purpose | Path |
|---|---|
| Post models (Entry, News, BlogPost, …) | `news/models.py` |
| AI summarization pipeline ⭐ | `news/tasks.py` |
| Summarization threshold constant | `news/constants.py` |
| Forms | `news/forms.py` |
| Views (incl. `V3AllTypesCreateView`) | `news/views.py` |
| URL for `/v3/news/add/` | `config/urls.py:273` |
| v3 create template ⭐ | `templates/news/v3/create.html` |
| Field include partials | `templates/v3/includes/_field_*.html` |
| WYSIWYG include | `templates/v3/includes/_wysiwyg_editor.html` |
| Icon set | `templates/includes/icon.html` |
| WYSIWYG source (rebuild required) | `frontend/wysiwyg-editor.js` → `static/js/v3/wysiwyg-editor.js` |
| Page CSS | `static/css/v3/create-post-page.css` |
| v3 gating | `core/mixins.py` (`V3Mixin`, `v3` waffle flag) |
| Authority checks (staff/moderator) | `news/acl.py` |
| OpenRouter settings | `config/settings` (`OPENROUTER_API_KEY`, `OPENROUTER_URL`) |

**Figma**: file `5j0fQssrV9ipoU16P7hfKy` — frame `7134-42434` (create-post),
`6635-24462` (Saving/Saved icon states), `1995-46463` (full deliverables board).
