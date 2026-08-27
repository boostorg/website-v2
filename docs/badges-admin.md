## How this section works

Badges are derived state, never typed in: a member earns achievements, and the
system derives their badges from the count of valid achievements against the
thresholds configured on the Badges page. Two pages describe the system
(Achievements and Badges), three describe a member (User achievements, User
badges and the per-member page), and the sync runs page is the audit log of the
automatic jobs. This page explains what each page and each operation is for, and
when to run it.

## The pages in this section

| Page | What it is for | What you do there |
| --- | --- | --- |
| **Achievements** | The catalogue of the eight achievement types: library authoring, library versioning, library maintenance, code commits, library review, documentation, mailing list and publisher. | Mostly read-only. The slug is the join key to the code that feeds a type, so it freezes once the row exists. Add a type only for a genuinely new achievement - a manual-only type needs no code, an automatic one needs a new source (a deploy). |
| **Badges** | One row per badge (Library Author, Version Author, Maintainer, Commits Master, Reviewer, Documenter, Regular, Publisher): the achievement that feeds it, its live ladder of thresholds, how many members hold it and whether an automatic source feeds it. | Opening a badge is one form: its description plus all active tiers, saved together. **This is where thresholds are changed** - see "Changing a badge's tiers" below. The Automatic column marks the sources that self-refresh; the other three badges only ever move on a manual grant. |
| **Badge tiers** | The history behind the ladder. Deliberately hidden from this index - tiers are configured on the badge page - and reached through a badge's "N retired tier(s)" link. | Recovery only: retired rows are listed here, and the Reactivate action undoes a mistaken retirement. The rows themselves are immutable. |
| **User achievements** | One row per achievement a member has earned. Automatic grants link to the row that justified them; manual ones carry the granting admin and their note. | The grant, correction and sync surface: add a manual grant (note required), invalidate or revalidate a grant (audited), and run the Backfill and Reconcile jobs. |
| **User badges** | The derived badge state, one row per badge tier a member holds or has held. A member who has climbed the ladder has a row per rank. Read-only, because only the recalculation service writes it. | Filter by Held / Revoked or by revocation source, follow the user link to the per-member page, revoke or reinstate a badge (audited), and run the Recalculate job. |
| **Per-member page** | One member's whole story, reached from the user link on either changelist: every achievement type with its valid and invalid grant counts, the rank held, the next rank with the gap, and a plain-English reason for the state. | The reason text tells you what is wrong and which fix it needs: "held below its threshold - recalculate", "grants already reach X - recalculate to award", "revoked by `<admin>` on `<date>`: `<note>`". Recalculate, Reconcile and Grant for that one member run here, synchronously. |
| **Achievement sync runs** | The read-only log of every backfill and reconcile run: what ran, when, what started it (command, admin or release pipeline) and who, and how many grants it added or removed. | Read only. A cascade revocation's note names the run that moved the count - when a member asks where their badge went, this is where the answer starts. |

## The operations and when to run them

Three jobs move the system: backfill, reconcile and recalculate. Backfill and
reconcile change achievements, and therefore badges; recalculate changes badges
only. All three are idempotent, and none of them notifies anybody - nothing in
this section emails a member.

| Operation | What it does | Where it lives | When to run it |
| --- | --- | --- | --- |
| **Backfill** | Walks the automatic sources and creates the achievements the site is missing, then awards any badge that reached a threshold. Additive only - it can never remove or undo an attribution, which is what makes it safe to run unattended. | "Backfill achievements" button on the User achievements page (one source or all, in the background), or `manage.py backfill_achievements` (`--source` for a single one, `--trigger` to label the run). | By itself: it is the last step of the weekly release pipeline (Saturday evenings), so every release refreshes the automatic achievements. Use the button when you wired a new source or an import just brought data you want counted now. Safe at any time - it only adds. |
| **Reconcile** | Two-way, the only operation that removes: it adds what a source now supports and deletes the stored grants it no longer does (a commit reassigned to another author, a news post deleted, a maintainer dropped, an account deleted), then recalculates the members that moved. You see a preview of the changes before anything runs. Manual grants are never touched. | "Reconcile achievements" button on the User achievements page (scoped like backfill), the per-member page, or `manage.py reconcile_achievements` with `--dry-run`, `--user`, `--source` or `--remove-only`. Requires the delete permission. | Not scheduled. Run it after an upstream data correction that backfill cannot undo - a fixed attribution, deleted content, a dropped maintainer, a deleted account - scoped to the member or source you meant to fix. A source that reads empty is treated as broken and nothing is removed; overriding that needs `--allow-empty` from the shell. |
| **Recalculate** | Rebuilds badges from the achievements already on record: awards every tier whose threshold is met and cascade-revokes every one that has fallen below it. No achievement is added, removed or changed - the safe thing to run after editing a badge's thresholds. Idempotent. | "Recalculate badges" button on the User badges page (whole table, in the background), or `manage.py recalculate_badges`. | After editing a badge's thresholds, after fixing data, after restoring a dump. Safe at any time. |
| **Recalculate / Reconcile this member** | The same two jobs for one member, run synchronously so the result is visible on the page you are already on. | Buttons at the bottom of the per-member page. | For a support request about one member. The page itself says which is needed: "held below its threshold" or "grants already reach X" call for a recalculate; a source disagreement calls for a reconcile. |
| **Manual grant** | Grants an achievement by hand for something no source can see (Documenter, Regular, and any special case). A note is required and the granting admin is recorded, and the member is not notified. | Add on the User achievements page, or "Grant an achievement" on the per-member page. | Whenever a member earned something the sources cannot derive. Backfill and reconcile never touch it. |
| **Invalidate / Revalidate** | Corrects a grant in place: invalidation soft-deletes it with a required note (who, when, why - the row stays for the audit trail), and the badge follows - cascade-revoked if the count drops below its threshold. Revalidate undoes it, clears the trail, and re-awards. | Select rows on the User achievements page and pick the action. | When a grant was wrong but must stay on record. There is no hard delete. |
| **Revoke / Reinstate** | The badge-side override: revoke takes a badge away with a required note; it survives every recalculation, and only reinstate brings it back. Reinstate skips cascade-revoked badges - their count is still below the threshold. | Select rows on the User badges page and pick the action. | When a member should not show a badge regardless of count - a policy decision, a dispute, a misused event badge. Never for correcting data: that is what invalidate and reconcile are for. |

> Each button runs one job at a time per scope: a backfill is refused while
> another backfill of the same source is queued or running, and the page shows
> the running job's status. Every real run - from a button or the release
> pipeline - is recorded on the sync runs page.

Two things the automatic sources deliberately pass over, both of which explain a
badge a member expected and does not have:

- **Deactivated accounts.** A deleted or disabled account is granted nothing,
  whatever the source data still says about it. Deleting an account scrubs its
  achievements, but the libraries and commits behind them are kept whole, so
  without this rule the next weekly backfill would award them all back. If such
  an account still holds grants from before, a reconcile removes them.
- **Sub-libraries.** `math/quaternion`, `functional/hash` and the rest count as
  part of their parent library, not as libraries of their own, so authoring or
  maintaining only a sub-library earns nothing. That is a product decision, and
  the work may get a badge of its own later.

## Changing a badge's tiers

Tiers are append-only records: they are never edited in place and never
hard-deleted. That rule is what keeps the "earned badges are not taken away"
promise, and the Badge page is the only place thresholds change.

1. Editing a threshold on the Badge page retires the old tier row and creates a
   replacement in the same save, inside one transaction. Removing a row on that
   page retires it too - "delete" means retire.
2. Retirement is a soft delete: the row stays, flagged inactive, with who
   retired it and when (recorded on the Badge tiers page).
3. Members who already earned the retired tier keep their badge: their badge
   row points at the retired tier, and recalculation only ever looks at active
   tiers. The new threshold applies to new earners only.
4. The Badge page says exactly this after each save: "Members who already
   earned X keep it; the new threshold applies from now on."
5. Why: updating a threshold in place would make the next recalculation
   cascade-revoke everyone who only ever reached the old number.
6. Undoing a retirement: the Badge tiers page lists retired rows with a
   Reactivate action. It refuses when the rank already has an active tier or
   the ladder would fall out of order - retire the replacement first.
7. The rules enforced at save time: one active tier per (badge, rank), and
   thresholds must climb bronze, silver, gold, platinum, diamond. A badge with
   no active tiers awards nothing, which the ladder column flags as "No tiers -
   awards nothing".
8. After any ladder change, run Recalculate so held state and next-rank hints
   match the new ladder.

## How revocation works

Revocation is always soft: the badge row stays, and who revoked it, when, why,
the source and the count at revocation are all recorded. Nothing is ever
deleted. There are two sources, and they behave differently.

|  | Cascade | Manual |
| --- | --- | --- |
| **What triggers it** | A recalculation found the member's valid count below the tier's threshold. | The revoke action on the User badges page, with a note. |
| **When it happens** | After an invalidation or revalidation, after a reconcile that removed grants, after a ladder change followed by a recalculate. | Whenever an admin decides a member should not show a badge, whatever the count. |
| **What it records** | The count, the rank and the threshold, plus the cause - the sync run that moved the count. | The admin and their note. |
| **Does it come back** | Yes - the next recalculation with the count back above the threshold re-earns it. A rank below one the member holds is never newly awarded, and a rank the member already has a row for is exempt, so a cascade-revoked rank returns when its own count recovers. | No - a manual revocation survives every recalculation. Only the reinstate action clears it. |
| **Where it shows** | User badges: the status filter (Held / Revoked) and the revocation source column. Per-member page: the State column and the reason text. | Same places, plus the note names the admin. |

> A manual revocation blocks even when a cascade revocation is also present: a
> member who had a badge cascade-revoked and then manually revoked needs the
> manual one cleared first. Reinstate refuses cascade-revoked badges - their
> count is still below the threshold - so grant or revalidate the achievements
> instead.
