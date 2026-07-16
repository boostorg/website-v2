# Storybook for Boost V3 Components

This project uses [storybook-django](https://github.com/torchbox/storybook-django) to develop and preview V3 UI components in isolation, powered by [Storybook](https://storybook.js.org/) on the frontend and [django-pattern-library](https://github.com/torchbox/django-pattern-library) on the backend.

---

## Running modes

There are two ways to use Storybook in this project:

| Mode | URL | When to use |
|---|---|---|
| **Dev server** | `http://localhost:6006` | Active development - live controls, instant re-render |
| **Served by Django** | `http://localhost:8000/storybook/` | Review / QA - pre-built bundle behind staff login |

---

## Mode 1: Dev server (active development)

### Prerequisites

- Python environment with project dependencies installed
- Node.js v18+

### Setup

**1. Install Python dependencies**

```bash
pip install django-pattern-library
```

Or rebuild from `requirements.in`:

```bash
pip-compile requirements.in
pip install -r requirements.txt
```

**2. Install Node dependencies**

```bash
npm install
```

### Running

#### Option A: Docker (recommended)

```bash
docker compose up --build
```

This brings up all services including `storybook` on [http://localhost:6006](http://localhost:6006). The Storybook container proxies to Django via `DJANGO_ORIGIN=http://web:8000` on the shared `backend` network.

To start only Storybook and its dependencies:

```bash
docker compose up --build storybook
```

#### Option B: Local (two terminals)

**Terminal 1 - Django:**

```bash
python manage.py runserver 8000
```

**Terminal 2 - Storybook:**

```bash
npm run storybook
```

Storybook opens on [http://localhost:6006](http://localhost:6006) and proxies template-rendering requests to Django on port 8000.

---

## Mode 2: Served by Django (staff-only, integrated)

The pre-built Storybook bundle is served directly by Django at `/storybook/`. Access requires a staff account — it uses the same session authentication as the rest of the site.

The pattern-library API endpoint (`/pattern-library/`) is also staff-gated by `PatternLibraryStaffMiddleware`, so template rendering works for authenticated staff users.

### Steps to build and serve

**1. Build the Storybook bundle**

With Docker (recommended):

```bash
docker compose run --rm storybook npx storybook build -o var/storybook
```

Or locally (requires Node.js):

```bash
npm run build-storybook
```

This outputs the static bundle to `var/storybook/` (excluded from git by the existing `var/` gitignore rule).

**2. Enable the pattern-library endpoint**

By default, the pattern-library is enabled when `DEBUG=True`. To enable it in a non-debug environment (e.g. staging), set the environment variable:

```bash
ENABLE_PATTERN_LIBRARY=true
```

In production, if you don't need the interactive template-rendering (i.e. you only need the Storybook UI itself for browsing), you can leave this unset — the `/storybook/` page will load but story renders will return errors. Typically you want both.

**3. Visit `/storybook/`**

Log in as a staff user and navigate to `/storybook/`. The full Storybook UI loads, including the controls panel and live template rendering via the gated `/pattern-library/` endpoint.

### Environment variables

| Variable | Default | Effect |
|---|---|---|
| `ENABLE_PATTERN_LIBRARY` | `DEBUG` value | Enable/disable the `/pattern-library/` endpoint and app registration |

### How the protection works

- `/storybook/` - served by `StorybookView` (in `core/views.py`), decorated with `@staff_member_required`. Non-staff users are redirected to login.
- `/pattern-library/` - gated by `PatternLibraryStaffMiddleware` (in `core/middleware.py`). Non-authenticated requests are redirected to login; authenticated non-staff get 403.
- The Storybook JS (running in the browser) calls `/pattern-library/render/` with the session cookie from the existing login session, so renders work transparently for staff users.

---

## Project structure

```
.storybook/
├── main.js           # Storybook config: story paths, addons, webpack
├── middleware.js      # Proxies /pattern-library/ requests to Django (dev server only)
└── preview.js         # Storybook preview parameters, theme sync

storybook/
├── mockData.js        # Shared mock data (authors, posts, events, badges)
└── components/        # Story files — one per component
    ├── Button.stories.jsx
    ├── Avatar.stories.jsx
    └── ...

templates/
└── patterns/
    └── base.html      # Base template for pattern-library rendering
                       # (loads V3 CSS, JS, fonts, Alpine, etc.)

var/storybook/         # Pre-built bundle output (gitignored)
```

---

## How it works

1. Each `.stories.jsx` file imports the `Pattern` React component from `storybook-django`.
2. `Pattern` sends a POST request to `/pattern-library/render/` with the **template path** and **context data**.
3. Django renders the template server-side and returns HTML.
4. Storybook displays the rendered HTML in its canvas with live controls.

In **dev server** mode, the `.storybook/middleware.js` proxy handles routing these requests to Django on port 8000. In **Django-served** mode, requests go to the same origin with no proxy needed.

---

## Adding a new component

### 1. Create the Django template

Place the template in `templates/v3/includes/`:

```
templates/v3/includes/_my_component.html
```

### 2. Create a story file

Create `storybook/components/MyComponent.stories.jsx`:

```jsx
import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/My Component",
  argTypes: {
    title: { control: "text" },
    variant: { control: "select", options: ["default", "green", "teal"] },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_my_component.html"
    context={{ title: args.title, variant: args.variant }}
  />
);
Default.args = { title: "Hello World", variant: "default" };
```

If the story needs shared data (authors, posts, events, badges), import from `storybook/mockData.js` rather than redefining inline.

### 3. Verify

With Django and Storybook running, the component appears automatically in the sidebar under **Components / My Component**.

---

## Tips

- **Controls**: Use `argTypes` to expose interactive knobs. Map each template variable to `text`, `select`, `boolean`, or `number`.
- **Complex context**: Pass full JS objects/arrays directly in the `context` prop for list/dict template variables.
- **Multiple variants**: Export multiple named functions from the same file for different states (empty, filled, themed).
- **Static assets**: The pattern-library base template (`templates/patterns/base.html`) loads all V3 CSS and JS. If you add new stylesheets or scripts, update that template.

---

## Configuration reference

| File | Purpose |
|---|---|
| `config/settings.py` | `ENABLE_PATTERN_LIBRARY`, `STORYBOOK_ROOT`, `PATTERN_LIBRARY` dict, middleware registration |
| `config/urls.py` | `/storybook/` (StorybookView) and `/pattern-library/` (conditional) URL registration |
| `core/views.py` | `StorybookView` — file-serving view with `@staff_member_required` |
| `core/middleware.py` | `PatternLibraryStaffMiddleware` — staff guard for `/pattern-library/` |
| `templates/patterns/base.html` | Base HTML shell for rendered patterns (CSS/JS/fonts) |
| `.storybook/main.js` | Storybook framework, story globs, webpack config |
| `.storybook/middleware.js` | Express proxy for API calls to Django (dev server mode only) |
| `.storybook/preview.js` | Storybook preview parameters, dark/light theme sync |
| `package.json` | `storybook` (dev) and `build-storybook` (outputs to `var/storybook/`) scripts |
| `requirements.txt` | `django-pattern-library` Python dependency |
| `docker/Dockerfile.storybook` | Storybook container image (Node 22) |
| `docker-compose.yml` | `storybook` service on `backend` + `frontend` networks |
