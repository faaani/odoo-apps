# Stale Records Report

Data quality rots quietly: leads nobody touched in a year, contacts last edited in 2019, products untouched since the import. Odoo has no screen that answers *what has not been touched lately?* — this module adds one. Point it at any model, pick an age, and get the counts by age together with the oldest records, their last-update date and the user who wrote them last.

## Features
- Works on **any model** that keeps a last-update date: contacts, leads, products, projects, your own custom models.
- **Counts by age bucket**: how many records are older than 30, 90, 180 and 365 days, plus the exact count for the age you asked for.
- **The oldest records listed** with their last-update date, how many days ago that was, and their last writer.
- **One click to the record**, or hand the whole selection over to the ordinary list view of that model.
- **Optional extra filter**: a literal Odoo domain such as `[("customer_rank", ">", 0)]`.
- **Archived records** included on request; excluded by default, like the standard list view.
- **Respects access rights**: every query runs as the current user, so record rules apply and the report can never show a record you could not open yourself. The screen says so.
- **Built for big tables**: counts are aggregate queries and the list is a single capped search (50 rows by default, 500 maximum), so the table itself is never read row by row - only the rows you asked to see. The cap is disclosed in the result.
- **Your report is yours**: the report rows are protected by a record rule, so one user can never read the results another user produced.
- **Strictly read-only**: it never writes to, archives or deletes the records it reports on. The only rows it stores are your own report parameters, in a temporary table Odoo clears by itself.

## Installation
1. Copy the module into your addons path (or install it from the Apps list).
2. Open Apps, remove the "Apps" filter, search for *Stale Records Report* and click Install.
3. Only the standard base module is required.

## Configuration
1. No configuration is needed.
2. The menu Settings &rarr; Stale Records Report is shown to Administration / Settings users.
3. The report itself may be used by any internal user, because it can never show more than that user is already allowed to see. To give it to a data-quality team, point a menu or action of your own at the `stale.records.wizard` model — no code change needed.

## Usage
1. Go to Settings &rarr; Stale Records Report.
2. Choose the Model (Contact, Lead, Product, ...) and the age in days — 90 by default.
3. Optionally add an Extra Filter as a literal Odoo domain, e.g. `[("customer_rank", ">", 0)]`, and tick *Include Archived Records* if archived rows should count too.
4. Set *Rows to List* (50 by default, 500 maximum) and press **Analyse**.
5. Read the counts, then work through the listed records — the arrow at the end of each row opens it. **Open All Stale Records** opens the complete selection in the normal list view, ready to filter, group or export.
6. **Change Criteria** returns to the form; **Refresh** re-runs the same analysis against today's data.

## What it does not do, and why
- **It never changes the records it reports on.** None of them is written, archived or deleted - not even the ones it lists. (The report does store your own criteria and result rows in a temporary table that Odoo clears by itself.) If you want stale records archived automatically, the companion module *Automatic Archiving Rules* (`auto_archive_stale_records`) does that on a schedule; it is a separate, optional install and this module neither depends on it nor installs it.
- **Counts are what *you* may see.** A user restricted by a record rule gets smaller numbers than an administrator on the same model. That is deliberate, and the report states it on screen.
- **Models without a last-update date cannot be reported on.** Abstract models, wizard (transient) models and the few models where Odoo disables log access have no `write_date`; they are refused with an explanation rather than reported as "nothing stale".
- **A model you cannot read is refused** instead of being counted for you.
- **"Last updated" is Odoo's `write_date`.** It changes whenever any field of the record is written — including by an automated job or an import — so a record touched only by a bulk update looks fresh. The *Last Updated By* column shows who that was.
- **The age buckets are cumulative.** A record untouched for 400 days is counted in all four; they do not slice the records into disjoint groups.
- **The extra filter is a literal domain.** Expressions such as `uid` or `context_today()` are not evaluated.

## Notes
Identical behaviour on every supported series (14.0 – 19.0). No developer mode required.

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
