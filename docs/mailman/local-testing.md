# Mailman - local development & testing

This walks through everything needed to stand up Mailman locally and manually test the
subscribe/confirm flow end to end.

## Part 1 - One-time infrastructure setup

1. **Uncomment `mailman-core` and `mailman-web`** in `docker-compose.yml` (commented out by
   default - they add weight to `docker compose up` that most devs don't need day to day).
2. **Confirm `MAILMAN_REST_API_URL`** in `.env` is set to:
   ```
   MAILMAN_REST_API_URL=http://lists.local.test:8001
   ```
   This is the default in `env.template`. `lists.local.test` is a network alias defined on the
   `mailman-core` service in `docker-compose.yml`, resolvable by `web`/`celery-worker`/
   `celery-beat` over Docker's internal network - no other setup is needed for it to work.
3. **Bring the stack up / restart it** so `web`, `celery-worker`, and `celery-beat` pick up the new
   env value - `.env` changes are not hot-reloaded:
   ```bash
   docker compose up -d
   ```
4. **Create the mailing lists** on your local Mailman instance:
   ```bash
   ./scripts/dev-mailman-helpers
   ```
   Pick `list lists` first - it should print nothing yet. Then run it again and pick
   `create lists`. Run `list lists` once more to confirm the three lists now exist
   (`boost.lists.local.test`, `boost-announce.lists.local.test`, `boost-users.lists.local.test`).

At this point your local Mailman is ready to accept subscriptions - infrastructure setup is done.

## Part 2 - Testing the subscribe → confirm flow

1. **Turn on the `v3` feature flag** so the V3 mailing-list card renders;
2. **Open a page with the mailing-list card** - either:
   - `http://localhost:8000/community/`, or
   - `http://localhost:8000/users/me/?edit=True` (logged in).
3. **Enter an email address in the card's subscribe field and submit it.** You should land back
   on the same page with a "pending confirmation" state shown on the card.
4. **Open Maildev** at `http://localhost:1080` - this is where local outgoing email lands instead
   of a real inbox. You should see a new "Confirm your Boost mailing list subscription"-style email
   addressed to the email you entered.
5. **Open the email and click the confirmation link** (or copy the `/mailing-list/confirm/<token>/`
   URL into your browser). You should land on a page reading **"Subscription confirmed"** listing
   the list(s) you subscribed to. If instead you see **"Could not subscribe - please try again
   later"**, see [Troubleshooting](#troubleshooting) below.
6. **Verify the subscription actually landed in Mailman**, independent of what the confirm page
   claims:
   ```bash
   ./scripts/dev-mailman-helpers   # pick "list members", then the list you subscribed to
   ```
   Your email address should appear in the roster.
7. **If you tested while logged in**, also check the same page again
   (`/users/me/?edit=True`) - the mailing-list card should now show the "already subscribed" /
   manage state instead of the subscribe form, confirming `UserMailingListSubscription` was
   updated to `ACTIVE`.

## Troubleshooting

- **Confirm page shows "Could not subscribe - please try again later" for every list** - almost
  always means `MailmanClient.subscribe()` couldn't reach Mailman. Check, in order:
  - Does `docker compose exec web python3 -c "import socket;
    print(socket.gethostbyname('lists.local.test'))"` resolve to an IP? If it errors, `web` isn't
    on the same network as `mailman-core`, or `mailman-core` wasn't recreated after you uncommented
    it - run `docker compose up -d mailman-core` again.
  - Did you restart `web`/`celery-worker`/`celery-beat` after changing `MAILMAN_REST_API_URL`?
  - Did you actually run `create lists` (Part 1, step 4)? If the lists don't exist yet on Mailman,
    every subscribe attempt fails the same way.
- **No email shows up in Maildev** - check `docker compose logs celery-worker` for a failed task;
  the confirmation email is sent via Celery, so the worker needs to be running.

## How list IDs are derived

- The app does **not** read list IDs from an env var. `mailing_list/constants.py` derives a
  `MAILMAN_DOMAIN` from the host of `MAILMAN_REST_API_URL`, then builds three list IDs from it:
  `boost.<domain>`, `boost-announce.<domain>`, `boost-users.<domain>`.
- Every consumer in the app (`mailing_list/mixins.py`, `mailing_list/views.py` - subscribe,
  confirm, manage, `managed_lists` filtering, etc.) uses this computed list.
- **Bottom line:** whatever host is in `MAILMAN_REST_API_URL` is the domain your local lists must
  actually exist under in Mailman.
- `scripts/dev-mailman-helpers`'s `create lists` action mirrors this same derivation in bash
  (`_mailman_domain()`), so there's nothing to keep in sync by hand - no `MAILMAN_LISTS` env var
  exists. The three prefixes live in a `LIST_PREFIXES` array at the top of the script; add more
  there if you need extra lists locally.

## Why `MAILMAN_REST_API_URL` needs a dotted domain, not `localhost`

- The host in `MAILMAN_REST_API_URL` doubles as the mail domain for every list (see above). A
  bare, single-label host like `localhost` or the Docker service name `mailman-core` gets past
  Mailman's *domain* creation, but list creation under it then fails with `"Invalid list posting
  address"` - Mailman requires the address to have at least two labels (a dot) to look like a
  real domain.
- It does **not** need to actually resolve over the public internet or be a real, owned domain -
  only the local network needs to resolve it, which is exactly what the `lists.local.test` network
  alias on `mailman-core` provides.
- If you need a different alias name (e.g. it collides with something on your machine), change it
  in both `docker-compose.yml`'s `mailman-core.networks.backend.aliases` and
  `MAILMAN_REST_API_URL` in `.env` - they must match.

## Why the email confirmation doesn't need Mailman's mail transport

- Mailman's own double opt-in is bypassed - `MailmanClient.subscribe()` sends
  `pre_verified`/`pre_confirmed`/`pre_approved: True`, so membership is created directly via the
  REST call.
- The confirmation email you see in Part 2 is this app's own signed token, sent through `maildev` -
  not through Mailman. Mailman's mail transport (LMTP/SMTP) doesn't need to work locally, only its
  REST API.
- `scripts/dev-mailman-helpers` also has `confirm pending` (accept pending Mailman-side
  subscription requests) - not normally needed given `pre_confirmed` above, but useful if a list
  isn't using it.
