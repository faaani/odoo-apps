# Overdue Activities Report

A read-only, cross-model report of the activities that are still open — who is
late, on which document, and by how many days.

Odoo shows each user their own late activities in the systray, and each document
its own activity list. There is no single place where a team leader can see what
the whole team is late on. This module adds that place.

## What you get

* **One row per open activity** with the assignee, the activity type, the
  summary, the document model, the live document name, the due date and the
  number of days overdue.
* **An Open button** on every row that jumps straight to the document.
* **Filters**: Overdue, Due Today, Due This Week (the next 7 days), Overdue 7+
  Days, Overdue 30+ Days, Assigned to Me, Scheduled by Me, plus a free
  "Overdue by at least N days" input.
* **Group by** assignee, activity type, document model, status or due date.
* **Pivot and graph views** with two measures: *Activities* (a count, for
  charting workload) and *Days Overdue* (averaged per group).

## How visibility works

The report never widens what you can already see, and it never runs as
superuser.

A row is shown to you when **either**:

1. the activity is assigned to you, **or**
2. you are allowed to read the document the activity is attached to.

Rule 2 is what lets a manager see the team: if you can read the leads, the
invoices or the tickets, you see the late activities on them. If you cannot read
a document, its activities stay hidden — the report re-checks the access rights
and record rules of every underlying document, with one query per model.

Rule 1 is the same exception Odoo itself applies to `mail.activity`: an activity
assigned to you is always visible to you, even when you cannot open the document
it points at.

Two consequences worth knowing:

* Access to the report itself is granted to every internal user (group
  *Employee*). What each of them actually sees is decided per row by the rules
  above.
* An activity whose document was deleted can no longer be checked against
  anything, so it stays visible only to the person it is assigned to. It is
  labelled *Deleted record* and its Open button reports a clear error instead of
  crashing.
* A row you can see only because of rule 1 shows no document link, because you
  are not allowed to open the document behind it. The Open button tells you so
  rather than failing with an access error.

## Limits, stated plainly

* Only **open** activities are reported. An activity that was marked done or
  cancelled never appears: Odoo deletes it, or (on the versions that keep done
  activities) archives it, and the report's database view excludes archived
  rows. There is no "done activities" history here.
* *Days Overdue* is counted in whole days against the current UTC date, the same
  reference Odoo uses for activity deadlines.
* The *Document Name (recorded)* column is the name Odoo stored on the activity
  when it was created and is not refreshed on rename; the *Document* column
  always shows the live name.
* The per-document visibility check examines at most 20,000 candidate rows per
  query. Above that backlog the check is truncated fail-closed: row lists,
  record counts, group totals and pivot measures can all come out lower than
  reality — never higher — and a warning is written to the server log. Narrow
  the filter (for example *Overdue 7+ Days*) to get exact numbers.
* The module is read-only. It creates a database view over `mail_activity` and
  writes to nothing: no activity, no document and no user is modified.

## Installation

1. Copy `activity_overdue_report` into your Odoo add-ons directory.
2. Restart the Odoo service.
3. Open **Apps**, click *Update Apps List*, search for **Overdue Activities
   Report** and press *Install*.

Dependencies: `mail` only (already installed on every Odoo database).

## Configuration

Nothing to configure — there are no settings and no scheduled action.

Access is granted to the *Employee* group on install. If you want to narrow it,
edit the access line for `activity.overdue.report` in
*Settings → Technical → Security → Access Rights* (developer mode) and point it
at your own group; the per-document visibility rules described above keep
applying on top of whatever you choose.

## Usage

1. Open the **Activities** menu in the main menu, then **Overdue Activities**.
2. The list opens filtered on *Overdue* and grouped by *Assigned To*, so you see
   immediately who is behind and by how much.
3. Use the *Document Model* group-by to see which part of the business is late,
   or the *Overdue 30+ Days* filter to isolate what has been ignored longest.
4. Click **Open** on a row to jump to the document and deal with the activity
   there — the report itself never changes anything.
5. Switch to the **pivot** or **graph** view to chart workload: put *Assigned
   To* in rows, *Activity Type* in columns and use the *Activities* measure.

## Support

Questions, bug reports and feature requests: **f.ashraf.dev1@gmail.com**

Author: Farhan Ashraf — <https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf
License: LGPL-3
