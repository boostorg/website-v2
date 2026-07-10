# QA Preview Deploy Automation — Proposal

## Purpose

Replace the manual, run-it-from-my-laptop QA preview process with a
PR-triggered GitHub Actions workflow, so QA no longer has to be at a
specific machine to spin up a staging preview of a pull request.

This proposal keeps the **single shared QA slot** (`cppal-dev`) as-is. It
automates *how a PR gets onto that slot*; it does not introduce per-PR
isolated environments.

---

## Current process (how it works today)

QA previews a PR by putting its code onto the `cppal-dev` branch of the
`cppalliance/website-v2-qa` fork, which triggers a GKE deploy into the
`cppal-dev` namespace.

### Step 1 — Manual, local script

`scripts/deploy-qa.sh <PR_NUMBER>` is run **by hand on the QA engineer's
machine**. For a given PR it:

1. Clones / updates the `cppalliance/website-v2-qa` fork under
   `~/qa-automation/`.
2. Adds `boostorg/website-v2` as the `upstream` remote.
3. Fetches the PR (`refs/pull/<N>/head`) into a local `pr/<N>` branch.
4. Checks out the fork's `cppal-dev` branch and either:
   - **default:** `git reset --hard` to the PR's commit, then
     `git push --force origin cppal-dev`, or
   - **`--merge`:** merges the PR branch and pushes normally.
5. Prompts for confirmation before pushing (unless `--yes`).

### Step 2 — CI/CD picks up the push

`.github/workflows/actions-gcp.yaml` (`CI-GCP`) has a `build` job that runs
only when:

```
github.repository == 'cppalliance/website-v2-qa'
  && github.event_name == 'push'
  && github.ref == 'refs/heads/cppal-dev'
```

When that push lands, the job:

- Builds the Docker image tagged with the short SHA and pushes it to
  Artifact Registry.
- Runs `helm upgrade --install -n cppal-dev -f values-cppal-dev-gke.yaml`
  (release `boost-cppal-dev`) against the `boostorg-cluster1` GKE cluster.
- Waits for rollout, then purges the Fastly CDN cache.

### Step 3 — QA reviews

The preview is served at **`cppal-dev.boost.cppalliance.org`** (see
`kube/boost/values-cppal-dev-gke.yaml`), where QA verifies the PR.

### Pain points

- **Machine-bound & manual.** Every PR requires the QA engineer to run a
  local bash script; nothing is triggered from the PR itself.
- **No feedback on the PR.** Reviewers can't see from the PR whether a
  preview is live or where.
- **Force-push on a shared branch.** `cppal-dev` is rewritten each time;
  whoever ran the script last owns the slot, with no record on the PR.
- **Serialized by nature.** Only one PR can occupy `cppal-dev` at a time —
  acceptable, but coordination is entirely out-of-band (Slack/verbal).

---

## Proposed automation

Move the logic of `deploy-qa.sh` **server-side into a GitHub Actions
workflow** that runs in `boostorg/website-v2`, triggered from the PR, and
that reports the preview URL back onto the PR. The single shared
`cppal-dev` slot and the existing deploy job are unchanged.

### Trigger — recommendation: **label-based**

Given the "not sure" on triggering, the recommended default is a
**label** (`qa` or `deploy-preview`):

- Visible in the PR UI; obvious who requested a preview and when.
- Easy to gate — only maintainers/QA can add labels.
- Natural teardown hook (label removed → optional reset).
- No parsing of comment bodies, no bot-command surface area.

Alternatives considered:

| Trigger | Pros | Cons |
|---|---|---|
| **Label `qa`** *(recommended)* | Visible, permission-gated, teardown-friendly | Requires label to exist in repo |
| Slash comment `/qa` | Chatops feel, works from mobile | Comment-parsing, needs author allowlist to avoid abuse |
| Auto on every PR | Fully hands-off | Thrashes the single shared slot; wasteful builds |

Because there is exactly **one** shared slot, auto-on-every-PR is a poor
fit (PRs would constantly overwrite each other). Label or slash-comment
both make "which PR owns the slot right now" an explicit, on-PR action.

### Flow

```
PR labeled `qa`
      │
      ▼
GitHub Actions (in boostorg/website-v2, `pull_request` / `labeled`)
  1. Check permission (actor is maintainer/QA)
  2. Check out PR head
  3. Push PR head → cppalliance/website-v2-qa `cppal-dev`
     (force-push, mirroring deploy-qa.sh default mode)
      │
      ▼
Existing CI-GCP `build` job fires on the cppal-dev push
  → build image, helm upgrade -n cppal-dev, purge Fastly
      │
      ▼
Workflow comments on the PR:
  "✅ QA preview deploying to https://cppal-dev.boost.cppalliance.org
   (commit <sha>)"
```

### What needs to exist

1. **New workflow file**, e.g. `.github/workflows/qa-preview.yml`, in
   `boostorg/website-v2`, triggered on `pull_request` (`types: [labeled]`)
   and gated on the label name.
2. **A cross-repo push credential.** The workflow must push to
   `cppalliance/website-v2-qa`. Today the QA engineer's local git
   credentials do this; automated, it needs a secret — a
   machine-user PAT or a GitHub App installation token with `contents:
   write` on the QA fork — stored as a repo/organization secret. **This is
   the main new secret to provision and the key decision to confirm with
   whoever administers the `cppalliance` org.**
3. **Permission gate** so only maintainers/QA can trigger a deploy
   (label events from forks otherwise run with limited tokens; using
   `pull_request_target` or a manual `workflow_dispatch` with the PR number
   are the two standard ways to get a privileged token — each has security
   tradeoffs called out below).
4. **A PR comment step** (`actions/github-script` or the `gh` CLI) to post
   the preview URL and status back.
5. *(Optional)* **Teardown / release step** on label removal or PR close —
   e.g. reset `cppal-dev` to `develop` so the slot returns to a known
   baseline and it's clear no PR currently owns it.

### Security considerations

- Pushing to another repo and building/deploying from PR code is
  privileged. Untrusted fork PRs must **not** get a deploy without an
  explicit maintainer action (the label *is* that action, but the workflow
  must verify the labeler's permission, not just the label's presence).
- Prefer a scoped GitHub App token over a long-lived PAT for the
  cross-repo push.
- Keep the deploy code path (build + helm) exactly as it is in
  `actions-gcp.yaml`; this proposal only changes *what puts code on
  `cppal-dev`*, so the blast radius of the deploy itself is unchanged.

### Explicitly out of scope

- **Per-PR isolated previews** (own namespace/URL per PR). That would need
  Helm value templating per PR, ingress/DNS wildcards, and teardown
  lifecycle — a substantially larger change. This proposal deliberately
  keeps the single shared `cppal-dev` slot.

---

## Rollout

1. Confirm trigger mechanism (recommend: `qa` label).
2. Provision the cross-repo push secret on `cppalliance/website-v2-qa`
   (App token preferred).
3. Add `.github/workflows/qa-preview.yml`, port `deploy-qa.sh` logic into
   it, add the permission gate and PR-comment step.
4. Keep `scripts/deploy-qa.sh` as the manual fallback during a trial
   period.
5. Optional follow-up: automatic teardown on label removal / PR close.

## Open questions for the team

- Who administers `cppalliance/website-v2-qa`, and can they mint an App
  token / machine-user PAT for the cross-repo push?
- Label vs. `/qa` comment — final call?
- Do we want automatic slot release (reset `cppal-dev` to `develop`) when a
  PR's label is removed or the PR is closed/merged?
