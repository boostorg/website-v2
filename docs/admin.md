# Admin Features

## LibraryVersions

- Button **Refresh Documentation Links** will re-run the task that retrieves the links to external documentation for every version of every Boost library.

## AI Description Settings

The "Auto-Generate Description" buttons on the v3 create-post page call a paid model, so each user gets a fixed number of generations per day. The cap is enforced by the endpoints themselves, not by hiding the button, so calling them directly does not get around it.

**Where**: Wagtail admin -> Settings -> AI Description Settings (`/cms/settings/news/aidescriptionsettings/`). It sits in the CMS beside the posts it governs. Editing it needs the `change_aidescriptionsettings` permission.

- **Daily limit** - generations per user per day, shared across both the body content and the link generator. Must be a positive whole number. A change applies from the next request; no deploy or restart.
- **Usage and history** - shown on the same screen: generations so far today, how many users were refused at the limit, and who last changed the limit, from what value to what. All counts cover the current UTC day and reset at midnight UTC.

**Exemptions**: superusers are always exempt. To exempt anyone else, add them to the `ratelimit_exempt` group at `/admin/auth/group/`. The group carries the `bypass_description_generation_limit` permission, which is what actually lifts the cap, so leave that permission attached. Exempt users' generations are still counted in the usage figures.

**Tuning the number**: every refusal is recorded, so the "users refused" figure shows whether the cap is biting. Rejections are also logged as `description_generation.rate_limited` events, separately from the per-attempt `description_generation.attempt` events.
