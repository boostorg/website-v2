# Storybook for Boost V3 Components

This project uses [storybook-django](https://github.com/torchbox/storybook-django) to develop and preview V3 UI components in isolation, powered by [Storybook](https://storybook.js.org/) on the frontend and [django-pattern-library](https://github.com/torchbox/django-pattern-library) on the backend.

## Prerequisites

- **Python environment** with the project's Django dependencies installed
- **Node.js** (v18+) and **npm**

## Installation

### 1. Install Python dependencies

```bash
pip install django-pattern-library
```

Or, if rebuilding from `requirements.in`:

```bash
pip-compile requirements.in
pip install -r requirements.txt
```

`django-pattern-library` is listed in `requirements.in`. The integration is **optional** — Django starts normally without it installed; the pattern-library app and URL are registered only when the package is detected.

### 2. Install Node dependencies

```bash
npm install
```

This pulls in `storybook`, `@storybook/react-webpack5`, `storybook-django`, `react`, and `react-dom` (all listed in `package.json` under `devDependencies`).

## Running Storybook

### Option A: Docker (recommended)

The simplest way — everything starts together:

```bash
docker compose up --build
```

This brings up all services including `storybook` on [http://localhost:6006](http://localhost:6006). The Storybook container automatically proxies to the Django `web` container via the `DJANGO_ORIGIN=http://web:8000` environment variable on the shared `backend` network.

To start **only** the storybook service and its dependencies:

```bash
docker compose up --build storybook
```

This will also start `web`, `db`, and `redis` (since `storybook` depends on `web`, which depends on `db` and `redis`).

### Option B: Local (without Docker)

You need **two terminals** — one for Django (backend renderer) and one for Storybook (frontend UI).

#### Terminal 1: Start Django

```bash
pip install django-pattern-library
python manage.py runserver 8000
```

Django must be running on port **8000** (the port configured in `.storybook/middleware.js`). The pattern-library API endpoint at `/pattern-library/` is what Storybook uses to render Django templates server-side.

#### Terminal 2: Start Storybook

```bash
npm install
npm run storybook
```

Storybook starts on [http://localhost:6006](http://localhost:6006). It proxies template-rendering requests to your running Django server.

## Project Structure

```
.storybook/
├── main.js          # Storybook config: story paths, addons, webpack
├── middleware.js     # Proxies /pattern-library/ requests to Django
└── preview.js       # Storybook preview parameters

storybook/
└── components/      # Story files — one per component
    ├── Button.stories.jsx
    ├── Avatar.stories.jsx
    ├── BasicCard.stories.jsx
    └── ...

templates/
└── patterns/
    └── base.html    # Base template for pattern-library rendering
                     # (loads V3 CSS, JS, fonts, Alpine, etc.)
```

## How It Works

1. Each `.stories.jsx` file imports the `Pattern` React component from `storybook-django`.
2. `Pattern` sends a request to Django's pattern-library API with the **template path** and **context data**.
3. Django renders the template server-side and returns the HTML.
4. Storybook displays the rendered HTML in its canvas with live controls.

## Adding a New Component

### 1. Create the Django template

Place your template in `templates/v3/includes/` following the existing naming convention:

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
    // Define Storybook controls for each template variable
    title: { control: "text", description: "Component heading" },
    variant: {
      control: "select",
      options: ["default", "green", "teal"],
      description: "Color variant",
    },
  },
};

export const Default = (args) => (
  <Pattern
    template="v3/includes/_my_component.html"
    context={{
      title: args.title,
      variant: args.variant,
    }}
  />
);
Default.args = {
  title: "Hello World",
  variant: "default",
};

// Add more variants as separate exports
export const GreenVariant = Default.bind({});
GreenVariant.args = {
  title: "Green variant",
  variant: "green",
};
```

### 3. Verify

With both Django and Storybook running, your new component appears automatically in the Storybook sidebar under **Components / My Component**.

## Tips

- **Controls**: Use `argTypes` to expose interactive knobs in Storybook's Controls panel. Map each template variable to a control type (`text`, `select`, `boolean`, `number`, etc.).
- **Complex context**: For list/dict context (e.g., `connections`, `testimonials`), pass full JS objects/arrays directly in the `context` prop.
- **Multiple stories**: Export multiple named functions from the same file to show different states of a component (empty vs. filled, different variants, etc.).
- **Composition**: You can nest `<Pattern>` components inside JSX to compose Django templates with React wrappers, useful for showing a component inside a layout.
- **Static assets**: The pattern-library base template (`templates/patterns/base.html`) loads all V3 CSS and JS. If you add new stylesheets or scripts, update that template.

## Building a Static Export

```bash
npm run build-storybook
```

This outputs a static build to `storybook-static/`. Note that because templates are rendered by Django, the static export still requires a running Django server to function. See the [storybook-django hosting docs](https://github.com/torchbox/storybook-django#hosting) for deployment strategies.

## Configuration Reference

| File | Purpose |
|---|---|
| `config/settings.py` | `PATTERN_LIBRARY` setting and `pattern_library` in `INSTALLED_APPS` (conditional) |
| `config/urls.py` | `pattern-library/` URL (conditional — only when package is installed) |
| `templates/patterns/base.html` | Base HTML shell for rendered patterns (CSS/JS/fonts) |
| `.storybook/main.js` | Storybook framework, story globs, webpack config |
| `.storybook/middleware.js` | Express middleware proxying API calls to Django (`DJANGO_ORIGIN` env var) |
| `.storybook/preview.js` | Storybook preview parameters |
| `package.json` | `storybook` and `build-storybook` scripts |
| `requirements.in` / `requirements.txt` | `django-pattern-library` Python dependency |
| `docker/Dockerfile.storybook` | Storybook container image (Node 22) |
| `docker-compose.yml` | `storybook` service on `backend` + `frontend` networks |

## Existing Components

The following V3 components have stories:

- **Button** — all style variants (primary, secondary, green, yellow, teal, error)
- **Button Tooltip** — all positions (top, right, bottom, left), icon-only
- **Avatar** — image, initials (yellow/green/teal), placeholder, all sizes
- **Basic Card** — one and two button variants
- **Horizontal Card** — image + text layout with CTA
- **Vertical Card** — image below text layout
- **Search Card** — with and without popular terms
- **Post Card** — with/without contributor badge
- **Post Cards List** — list layout with multiple cards
- **Banner** — default and auto-fade variants
- **Learn Card** — links list with hero image
- **Testimonial Card** — carousel of quotes
- **Account Connections Card** — mixed, all connected, none connected
- **Badges Card** — empty with/without CTA, filled (2 and 6 badges)
- **Create Account Card** — rich text body with preview image
- **Form Inputs** — text field, icon, error, checkbox, combo box, multi-select
- **Dialog** — modal with/without description
- **Content Detail Card** — with icon, link, CTA, plain
- **Content Event Card** — list and card variants
- **Achievement Card** — empty and filled states
- **Why Boost Cards** — grid of content-detail cards
- **Mailing List Card** — email subscription form
- **Install Card** — tabbed package manager / system install
- **Code Blocks** — standalone and card variants
- **Carousel Buttons** — prev/next controls
- **Cards Carousel** — default, autoplay, infinite+autoplay
- **Thread Archive Card** — mailing list archive links
- **Event Cards** — all color variant gallery
- **Category Tags** — all size/color variants with version tags
