# Component Workflow

This document describes the process for adding, previewing, and maintaining UI components in the Boost website v3 design system.

## Overview

We use [django-lookbook](https://django-lookbook.readthedocs.io/) as our component storybook. It provides:

- **Live previews** — each component is rendered in an isolated iframe at `/lookbook/`
- **Auto-discovery** — preview files in the `previews/` directory are detected automatically
- **Documentation** — docstrings on preview methods are rendered as Markdown in the "Notes" tab
- **Source inspection** — the generated HTML source is visible alongside the preview

## Directory structure

```
previews/
├── __init__.py
├── buttons_preview.py        # Buttons & hero buttons
├── avatars_preview.py        # Avatar component
├── tooltips_preview.py       # Tooltip buttons
├── cards_preview.py          # Basic, Vertical, Search, Create Account,
│                             #   Learn, Testimonial, Post, Mailing List,
│                             #   Thread Archive, Library Intro cards
├── forms_preview.py          # Text field, Checkbox, Combo, Multi-select
├── carousel_preview.py       # Carousel buttons & Cards carousel
├── content_preview.py        # Content detail card, Content event card,
│                             #   Why Boost cards, Event cards, Category tags
├── code_blocks_preview.py    # Code block, Code block card, full story layout
├── stats_preview.py          # Stats in numbers (bar charts)
└── template_preview.py       # (empty, kept for reference)

templates/
├── django_lookbook/
│   └── preview.html          # Wrapper template for all lookbook previews
│                             #   (loads v3 CSS, Alpine.js, highlight.js, etc.)
└── v3/
    └── includes/             # The actual component templates
        ├── _button.html
        ├── _avatar_v3.html
        └── ...
```

## Adding a new component

### 1. Create the component template

Add a new partial template in `templates/v3/includes/`:

```
templates/v3/includes/_my_component.html
```

Follow the existing conventions:
- Prefix with `_` (Django partial convention).
- Add a `{% comment %}` block at the top documenting all variables, their types, whether they're required, and a usage example.
- Use BEM-style class names scoped to the component (e.g. `my-component__title`).

### 2. Add the component CSS

Create a CSS file in `static/css/v3/`:

```
static/css/v3/my-component.css
```

Then import it in `static/css/v3/components.css`:

```css
@import './my-component.css';
```

### 3. Write a lookbook preview

Create a new preview file (or add to an existing one if the component belongs to a logical group):

```python
# previews/my_component_preview.py

from django_lookbook.preview import LookbookPreview
from django.template.loader import render_to_string


class MyComponentPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Brief description of what this preview shows.

        Template: `v3/includes/_my_component.html`

        | Variable | Required | Description |
        |---|---|---|
        | `title` | Yes | Component heading |
        | `description` | No | Body text |
        """
        return render_to_string("v3/includes/_my_component.html", {
            "title": "Example title",
            "description": "Example description text.",
        })

    def another_variant(self, **kwargs):
        """
        Description of this variant (e.g. different theme, size, or state).
        """
        return render_to_string("v3/includes/_my_component.html", {
            "title": "Variant title",
            "description": "Shows a different configuration.",
        })
```

**Conventions for preview files:**

- **One `LookbookPreview` subclass per component** (or per tightly related group).
- **Each public method = one preview** in the lookbook sidebar.
- **Method names** should be descriptive: `default`, `with_icon`, `error_state`, `few_items`, etc.
- **Docstrings** are rendered as Markdown in the lookbook Notes tab. Include:
  - A brief description of what the preview demonstrates.
  - The template path.
  - A table of the component's variables (for the primary/default preview).
- **Use `render_to_string`** when passing context variables. Use `Template(...).render(Context({...}))` when you need inline template logic (e.g. `{% include %}` with `with` parameters).
- **Don't invent documentation** — only document variables that actually exist in the template's `{% comment %}` block.

### 4. Verify in the lookbook

Start the dev server and visit:

```
http://localhost:8000/lookbook/
```

Your new preview should appear automatically in the sidebar. Check:

- The preview renders correctly in the iframe.
- The HTML source tab shows the expected markup.
- The Notes tab shows your docstring documentation.

### 5. For components with hover / active states

Two approaches:

- **Interactive** (preferred): Let the user hover naturally in the lookbook preview iframe.
- **Forced state**: Add a separate preview method (e.g. `hovered_buttons`) that applies a `data-hover` attribute or equivalent CSS class to force the visual state. This is useful for visual regression testing and design review.

Both approaches can coexist — the default preview for interactive testing, and a forced-state preview for static screenshots.

### 6. Preview template (`django_lookbook/preview.html`)

All previews are rendered inside `templates/django_lookbook/preview.html`. This template loads:

- V3 component CSS (`static/css/v3/components.css`)
- Alpine.js (for interactive components like dropdowns, tooltips)
- highlight.js (for code blocks)
- carousel.js (for carousel behaviour)
- Google Fonts (Noto Sans)

If your component requires additional JS or CSS, add it to this template.

## Components not in lookbook

- **WYSIWYG editor** (`v3/includes/_wysiwyg_editor.html`) — This component requires TipTap JS initialization via a dynamic module import (`/static/js/v3/wysiwyg-editor.js`) and custom inline scripts for demo content. It is better tested in-context (e.g. in the Django admin or a dedicated test page) rather than in an isolated lookbook preview.

## Checklist for new components

- [ ] Template created in `templates/v3/includes/` with `{% comment %}` documentation
- [ ] CSS file created in `static/css/v3/` and imported in `components.css`
- [ ] Lookbook preview written in `previews/` with docstring documentation
- [ ] Preview renders correctly at `/lookbook/`
- [ ] All component variants have dedicated preview methods
- [ ] Any required JS is loaded in `templates/django_lookbook/preview.html`
