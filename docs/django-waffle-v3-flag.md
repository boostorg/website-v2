# Django Waffle — Feature flags

This document describes how **feature flags** work in the Boost website project (django-waffle), how to assign and manage them, and how the **v3** flag is set up.

---

## How feature flags work in this project

- **Library:** [django-waffle](https://github.com/jazzband/django-waffle) (v5.0.0). Flags are stored in the database and evaluated per request (and optionally per user, group, or session).
- **Middleware:** `waffle.middleware.WaffleMiddleware` runs on each request so that flag state is available in templates and views.
- **Settings** (`config/settings.py`):
  - **`WAFFLE_CREATE_MISSING_FLAGS = True`** — The first time a flag name is used in code (e.g. `{% flag "v3" %}` or `flag_is_active(request, "v3")`), it is auto-created in the database with default **off**.
  - **`WAFFLE_FLAG_DEFAULT = False`** — Newly created flags have “Everyone” = No; they only become active when explicitly enabled for users, groups, percentage, etc.
- **Evaluation:** For each request, waffle checks the flag’s rules (everyone, superusers, staff, authenticated, groups, users, percentage, testing cookie). If any rule matches, the flag is **active** for that request; otherwise it is **inactive**. Anonymous users only get a flag if “Everyone” is Yes or a percentage/testing rule applies; group-based activation applies only to authenticated users in the chosen groups.

So in short: **flags are off by default**, and you turn them on by assigning **groups**, **users**, or other options in the Django admin.

---

## How to assign feature flags

Feature flags are managed in the **Django Admin** under **Waffle**.

### 1. Create or open a flag

- Go to **Django Admin** → **Waffle** → **Flags** (`/admin/waffle/flag/`).
- Either:
  - **Create** a new flag (Name = e.g. `v3`), or
  - **Open** an existing flag (e.g. `v3`).

With `WAFFLE_CREATE_MISSING_FLAGS = True`, the flag may already exist because it was used in code; you only need to edit it.

### 2. Choose who gets the flag

On the flag’s edit page you can enable the flag for:

- **Everyone** — Yes/No/Unknown. “Yes” turns the flag on for all requests (use with care).
- **Superusers** — If checked, the flag is always on for superusers.
- **Staff** — If checked, the flag is on for staff users.
- **Authenticated** — If checked, the flag is on for any logged-in user.
- **Groups (Chosen groups)** — The flag is on only for users who belong to at least one of the selected groups. This is the usual way to target testers (e.g. `v3_testers`).
- **Users (Chosen users)** — The flag is on only for the selected users.
- **Percentage** — Roll out to a percentage of users (0.0–99.9).
- **Testing** — When enabled, the flag can be toggled via a query/cookie for testing (see waffle docs).

For a **group-based** flag (e.g. v3):

1. In **Chosen groups**, move the desired group (e.g. **v3_testers**) from “Available groups” to “Chosen groups”.
2. Leave **Everyone** as “No” (or “Unknown”) so only the chosen group sees the flag.
3. Click **Save**.

### 3. Put users into the group

Group-based flags only apply to **authenticated** users who are **members** of one of the chosen groups.

- Go to **Users** (or **Auth** → **Users** / **Users** → **Users**, depending on your project).
- Open the **user** that should see the flag.
- In **Groups** (or “User groups”), add the group (e.g. **v3_testers**).
- Save.

After that, when that user is logged in, the flag is active for their requests. Log out and back in (or use a fresh session) if you don’t see the change.

---

## The “v3” flag and banner

The **v3** flag is used to show a banner to users who are part of the v3 rollout.

### What was added in the repo

- **django-waffle** in `requirements.txt` (v5.0.0).
- **Config** in `config/settings.py`: `waffle` in `INSTALLED_APPS`, `waffle.middleware.WaffleMiddleware` in `MIDDLEWARE`, `WAFFLE_CREATE_MISSING_FLAGS = True`, `WAFFLE_FLAG_DEFAULT = False`.
- **Banner** in `templates/base.html`: `{% load waffle_tags %}` and a block `{% flag "v3" %} ... {% endflag %}` that shows a grey “v3 flag enabled” bar at the top of the page when the flag is active for the requesting user.
- **Data migration** `users/migrations/0021_add_v3_testers_group.py` creates the Django auth group **v3_testers**, which can be assigned to the v3 flag.

### How to enable the v3 banner for yourself

1. **Apply migrations** (so the `v3_testers` group exists):
   ```bash
   just migrate
   # or: docker compose run --rm web python manage.py migrate
   ```
2. **Admin** → **Waffle** → **Flags** → open (or create) the **v3** flag.
3. In **Chosen groups**, add **v3_testers** and save.
4. **Admin** → **Users** → open **your user** → add **v3_testers** to Groups → save.
5. Log in on the site and reload; the **“v3 flag enabled”** banner should appear at the top.

### If the “v3 flag enabled” banner does not appear

- You must be **logged in**; group-based flags do not apply to anonymous users.
- Your **user** must be in the **v3_testers** group (Users → your user → Groups).
- **Log out and log back in** (or use a new incognito session) so the session reflects the group.
- Confirm the **v3** flag is saved with **v3_testers** in Chosen groups.

---

## Where it is in the codebase

| What | Where |
|------|--------|
| Conditional banner | `templates/base.html`: `{% load waffle_tags %}` and `{% flag "v3" %} ... {% endflag %}` |
| Waffle config | `config/settings.py`: `INSTALLED_APPS`, `MIDDLEWARE`, `WAFFLE_*` |
| v3_testers group | `users/migrations/0021_add_v3_testers_group.py` |
| Package | `requirements.txt`: `django-waffle==5.0.0` |

---

## Using flags in Python (views)

```python
from waffle import flag_is_active

def my_view(request):
    if flag_is_active(request, "v3"):
        # Flag is active for this request (e.g. user in v3_testers)
        ...
    else:
        ...
```

---

## Using flags in templates

```django
{% load waffle_tags %}

{% flag "v3" %}
  <div>Content only shown when the v3 flag is active for this user.</div>
{% endflag %}
```

You can use the same pattern for any flag name (e.g. `{% flag "my_feature" %}`) and assign it via groups or users in the admin as described above.
