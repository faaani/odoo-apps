# Automatic Archiving Rules

Lost leads from three years ago, tasks closed last winter, contacts nobody has touched since the import — Odoo keeps every one of them in every list, every dropdown and every report, forever. There is no built-in way to archive them on a schedule, so lists only ever grow.

This module lets you define archiving rules: pick a model, add an optional filter, say how long a record may stay untouched, and a daily scheduled action does the rest.

## Features
- Works on any model with an Active field: leads, tasks, contacts, products, your own models.
- Optional extra domain, combined with the age condition, so a rule targets exactly what you mean.
- Preview button: opens the exact records the next run would archive, and changes nothing.
- Per-rule counters: last run, archived on last run, total archived.
- One daily scheduled action applies every enabled rule; Run Now is there when you do not want to wait.

## Safety
Archiving hides records, so the module is deliberately cautious:
- every new rule is disabled until you turn it on;
- a minimum age is enforced in code, so a mistyped 0 can never empty a list;
- users, companies and technical (ir.*) models are refused outright — and so are the contact records behind a user or a company, even on a plain "stale contacts" rule;
- a model with no Active field is rejected when the rule is saved, as is a filter that does not apply to it;
- one record that cannot be archived is logged and skipped, it never aborts the run;
- only administrators (Settings access) can see or edit rules.

## Installation
1. Open Apps, search for Automatic Archiving Rules and click Install.
2. Only the standard base module is required — no other dependency.
3. Installing creates one scheduled action, "Automatic Archiving: apply archiving rules". It has nothing to do until you create a rule.

## Configuration
1. Enable the developer mode, then go to Settings > Technical > Automation > Automatic Archiving.
2. Click New and name the rule, for example "Leads with no activity for 6 months".
3. Choose the Model. Models without an Active field, and protected models such as Users, Companies and technical ir.* models, are refused with an explanation.
4. Optionally set an Additional Filter with the domain editor to narrow the rule down.
5. Set Archive After (days) — how long a record may go without being modified. Values under the built-in minimum are raised to it.
6. Leave Enabled off for now.

## Usage
1. On the rule, click Preview. The exact records the rule matches open in a list — nothing is modified.
2. Happy with the list? Switch Enabled on. The daily scheduled action will apply the rule from then on.
3. In a hurry, click Run Now to archive the matching records immediately.
4. Last Run, Archived on Last Run and Total Archived tell you what the rule has been doing.
5. Archived records are never deleted: any list shows them again with the standard Archived filter, and they can be restored.
6. To pause a rule, switch Enabled off; to retire it, archive or delete the rule itself.
7. A rule applies to every company in the database — add a company condition to the filter if you want to limit it — and archives at most a few thousand records per run, continuing on the following days until it has caught up.

## Notes
Identical behavior on every supported series (14.0 – 19.0). The scheduled action is configured per series so it keeps running instead of firing once.

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
