# QA Modernization Playbook

**Pilot project:** `boostorg/website-v2` · **Status:** discussion draft ·
**Audience:** Product / QA

The QA workflow on the Boost website is a chain of manual steps performed by
one person. This document maps that chain, interprets what "automation"
actually means here, and lays out a phased plan to remove the human from the
mechanical links — shaped so the result becomes a QA practice Metalab can
reuse on the next client, not a one-off fix.

---

## The reframe

When a PM says *"automation,"* they don't mean a specific tool — they mean an
**outcome**: *"I shouldn't have to wait on one person clicking through every
PR, and I want to see that a change works without asking someone."* The
complaint is that **QA sits in the critical path as a human bottleneck**, and
that the proof a change works is a person's hand-pasted screenshots — which
don't scale, aren't repeatable, and stall the moment that person is out.

With the context that **Metalab is continually improving QA for its clients —
through new tools, AI, and automation** — this stops being a one-off fix and
becomes a **capability**. The deliverable is a repeatable QA pattern the
studio can demonstrate and reuse, piloted here because Boost already has most
of the plumbing (a preview pipeline and Playwright already in the repo).

At a glance:

- **6 of 7** steps in the QA chain are done by hand.
- **1** step is automated today — the Helm deploy.
- **Playwright 1.58** already ships in `requirements.txt`, unused for QA.
- **3** levers named by the team: tools · AI · automation.

---

## 1. The QA chain today

QA previews a PR by putting its code onto the `cppal-dev` branch of the
`cppalliance/website-v2-qa` fork, which triggers a GKE deploy. Every link
except the deploy engine itself is a person.

| # | Step | State |
|---|------|-------|
| 01 | **Decide a PR needs QA** — coordinated over Slack/verbally; nothing on the PR records it. | 👤 Manual |
| 02 | **Get the PR onto staging** — QA runs `scripts/deploy-qa.sh <PR#>` locally, force-pushing the PR commit onto `cppal-dev`. | 👤 Manual |
| 03 | **Build & deploy to the cluster** — the push triggers CI-GCP: build image, `helm upgrade` into the `cppal-dev` namespace, purge CDN. | ⚙ **Automated** |
| 04 | **Verify the change** — a person opens `cppal-dev.boost.cppalliance.org` and clicks through the flow in light/dark/mobile. | 👤 Manual |
| 05 | **Produce evidence** — screenshots captured by hand and pasted into the PR's `## Screenshots` grid (see PRs #2482, #2475, #2481). | 👤 Manual |
| 06 | **Write test steps & sign off** — a numbered "peer-review testing" walkthrough is typed and the checklist ticked (sometimes skipped). | 👤 Manual |
| 07 | **Release the shared slot** — one `cppal-dev` slot, no teardown; which PR "owns" staging lives out-of-band. | 👤 Manual |

### How steps 02–03 work in detail

`scripts/deploy-qa.sh <PR_NUMBER>` is run by hand on the QA engineer's
machine. It:

1. Clones/updates the `cppalliance/website-v2-qa` fork under
   `~/qa-automation/` and adds `boostorg/website-v2` as the `upstream` remote.
2. Fetches the PR (`refs/pull/<N>/head`) into a local `pr/<N>` branch.
3. Checks out the fork's `cppal-dev` branch and either:
   - **default:** `git reset --hard` to the PR's commit, then
     `git push --force origin cppal-dev`, or
   - **`--merge`:** merges the PR branch and pushes normally.
4. Prompts for confirmation before pushing (unless `--yes`).

`.github/workflows/actions-gcp.yaml` (`CI-GCP`) then runs its `build` job on
the `cppal-dev` push (gated on
`github.repository == 'cppalliance/website-v2-qa' && github.ref == 'refs/heads/cppal-dev'`):
build the image, `helm upgrade --install -n cppal-dev -f values-cppal-dev-gke.yaml`
(release `boost-cppal-dev`) on `boostorg-cluster1`, then purge Fastly. The
preview is served at **`cppal-dev.boost.cppalliance.org`**.

### Why it hurts

- **Machine-bound & manual** — nothing is triggered from the PR itself.
- **No feedback on the PR** — reviewers can't see whether a preview is live.
- **Force-push on a shared branch** — whoever ran the script last owns the
  slot, with no record on the PR.
- **Evidence is hand-made** — screenshots and test notes are assembled by a
  person, and checklist items get skipped.

---

## 2. What "automation" most plausibly means

The trap: an engineer hears "automation" and builds a clever test suite,
while the PM's daily pain is waiting on a person to press a button. Ranked by
how likely each is the real ask:

1. **Self-serve, PR-triggered previews** *(most likely).* A preview comes up
   from the PR itself — a label or a button — with the URL posted back, no
   named person running a laptop script. Removes steps 01–03 and takes QA out
   of the gate.
2. **Automated evidence instead of hand-pasted screenshots.** Screenshots
   across light/dark/mobile generate themselves in CI and land on the PR.
3. **An automated pass/fail signal.** A check that goes red when a change
   breaks a page — the leap from "here's what it looks like" to "the system
   says it's good."
4. **The whole loop, hands-off.** Open PR → deploy → verify → post results →
   set status → release the slot, human only for judgment calls.

---

## 3. Three levers: tools, AI, automation

The team named the categories themselves. What each realistically buys:

### Automation *(deterministic — highest ROI, do first)*
- PR-triggered preview deploy (removes the human-as-gate).
- Auto-captured screenshots + visual-regression check posted to the PR.
- Auto-run of the changed flows on the live preview.

### New tools *(enablers)*
- **Playwright** — already in `requirements.txt` (1.58), Chromium already
  wired in CI. E2E + built-in `toHaveScreenshot()` visual diffing.
- Baseline snapshots so "did the UI change?" is a reviewable diff, not a human
  comparison.

### AI *(accelerant — keep it assisting the deterministic checks, not replacing them)*

**Useful today:**
- Draft the per-PR test plan from the diff + description (the "peer-review
  testing steps" are already hand-written on every PR).
- Vision-model review of screenshots (cut-off, contrast, overflow) — maps to
  the "matches Figma / a11y" checklist items.
- Triage a red run: real regression vs. flaky selector.

**Handle with caution:**
- Fully autonomous "self-healing" agents that decide pass/fail with no
  baseline — flaky, and a sign-off nobody can reproduce is worse than a manual
  one.

The honest framing: **AI writes and triages the tests; automation runs them
deterministically; the tools do the diffing and reporting.**

---

## 4. Phased pilot roadmap

Sequence matters. Phases 1–2 remove the toil and each demos on its own; phase
3 is the differentiator Metalab can market — but bolting AI on before the
deterministic base exists just yields unreliable magic.

### Phase 1 — Deploy automation *(removes steps 01–03)*

A PR-triggered workflow does what `deploy-qa.sh` does, server-side, and
comments the preview URL back on the PR. Keeps the single shared `cppal-dev`
slot.

- **Trigger — recommended: `qa` label.** Visible in the PR UI,
  permission-gated, teardown-friendly, no comment-parsing. Auto-on-every-PR is
  a poor fit given the single shared slot; a `/qa` comment is the alternative.
- **What needs to exist:**
  1. New workflow `.github/workflows/qa-preview.yml` in `boostorg/website-v2`,
     on `pull_request` (`types: [labeled]`), gated on the label.
  2. **A cross-repo push credential** to write to `cppalliance/website-v2-qa`
     — a GitHub App installation token (preferred) or machine-user PAT with
     `contents: write`. *This is the main new secret to provision and the key
     decision to confirm with whoever administers the `cppalliance` org.*
  3. **Permission gate** so only maintainers/QA trigger a deploy (verify the
     labeler's permission, not just the label's presence).
  4. **PR comment step** posting the preview URL + status.
  5. *(Optional)* **teardown** on label removal / PR close — reset `cppal-dev`
     to `develop` so it's clear no PR owns the slot.
- **Security:** building/deploying from PR code is privileged; untrusted fork
  PRs must not deploy without an explicit maintainer action. Keep the
  build+helm path exactly as it is in `actions-gcp.yaml` — this phase only
  changes *what puts code on `cppal-dev`*, so the deploy's blast radius is
  unchanged.

### Phase 2 — Verification automation *(removes steps 04–06)*

Playwright drives the changed pages across light/dark/mobile, captures
screenshots, diffs them against a committed baseline, and posts the images + a
pass/fail check to the PR. The `## Screenshots` grid fills itself and the
check becomes a real regression gate. Uses tooling already in the repo.

### Phase 3 — AI layer *(assists steps 04–06)*

An LLM drafts the test plan from the PR diff/description and triages failures;
optional vision-model review covers the "matches Figma / a11y" checklist
items. This is the differentiator for the Metalab QA offering.

---

## 5. Before we build — two things to confirm

- **Where's the real pain?** Is it "it's too slow/manual to get a preview up"
  (→ ship Phase 1 now) or "I don't trust hand-pasted screenshots as proof"
  (→ lead with Phase 2/3)? Same components, different first deliverable — the
  one ambiguity the code can't resolve.
- **Boost fix, or Metalab offering?** A "make Boost's QA less painful" mandate
  means ship Phases 1–2 as-is. A "build the studio's QA capability" mandate
  means design Phases 2–3 for **portability** from day one, so it drops onto
  the next client.

### Operational open questions

- Who administers `cppalliance/website-v2-qa`, and can they mint an App token /
  machine-user PAT for the cross-repo push?
- Label vs. `/qa` comment — final call?
- Do we want automatic slot release (reset `cppal-dev` to `develop`) when a
  PR's label is removed or the PR is closed/merged?
