# Followers Audit Report

Nobody knows why they get so many Odoo notifications. Follower subscriptions pile up quietly on every model and there is no single place to look at them. This module adds two read-only reports over `mail.followers`: who follows the most records and on which document types, and which records have an unusual number of followers.

## Features
- **Followers by Person** — one line per contact and document type, with the number of records followed on that type and the total across all types.
- **Records by Follower Count** — the records with the most followers first, so the document that mails half the company is easy to spot.
- Internal users vs contacts: a filter that separates colleagues with a user account from address-book contacts and portal users.
- Minimum-count filters on both reports: ready-made thresholds (5 / 25 / 100 records followed, 5 / 10 / 25 followers per record) plus a free "at least N" input.
- Filter and group by document type, follower, or follower type; export either report to spreadsheet.
- Drill-down: **Open Followed Records** opens those records in their standard view, **Open Record** opens a single record — where the chatter's *Followers* button is Odoo's normal way to unsubscribe someone.
- Aggregated with `read_group` over `mail.followers`, ranked and limited by the database itself — no per-record loop, and no million-row result assembled in memory just to display the top of it. Partner names, model labels and record names are resolved in bulk.
- Restricted to the Administration / Settings group (`base.group_system`), because follower data spans every model in the database.

## Installation
1. Copy the module into your addons path (or install it from the Apps list).
2. Open Apps, remove the "Apps" filter, search for *Followers Audit Report* and click Install.
3. Only the standard `mail` module is required.

## Configuration
1. No configuration is needed — both reports work as soon as the module is installed.
2. Access is restricted to users in the Administration / Settings group.
3. Optional: each run ranks at most 2000 followers (resp. 2000 records) and stops there — the limit is applied by the database, not after loading everything. Set the system parameter `followers_audit_report.line_limit` (Settings → Technical → System Parameters) to another number, or to `0` for no limit. When the cap applies, the report title says so, e.g. *Records by Follower Count (top 2000)*.

## Usage
1. Go to **Settings → Followers Audit → Followers by Person**. The list opens with the heaviest followers first.
2. Filter on *Internal Users* or *Contacts*, on a document type, or type a number in *Records on this document type (at least)*.
3. Group by **Follower** for one line per person, or by **Document Type** to see where the subscriptions live.
4. Click **Open Followed Records** to open those records in their own view, then use the chatter's *Followers* button on a record to unsubscribe someone.
5. Go to **Settings → Followers Audit → Records by Follower Count** for the other angle, with *Open Record* on every line.
6. Select all and use Export to take either report into a spreadsheet.

## What this module does not do
- It never writes: no follower row, no record, no user, no subscription is created, changed or deleted. There is deliberately no mass-unsubscribe button — unsubscribing happens in the record's chatter, one record at a time.
- Each report is a snapshot rebuilt every time you open the menu. It is not a live view and it is not stored.
- Follower rows can outlive the record they point at, or point at a model whose module was uninstalled. Those lines are reported with *Record Exists* unticked and cannot be opened — they are shown, never cleaned up.
- *Internal User* means the contact owns a non-portal user account (archived accounts included). Portal and public users are reported as contacts.
- Counts come from the follower rows, which carry no access rules of their own. A record your own rights hide from you is therefore still counted — but it is shown as *Document #id*, flagged *Record Exists* unticked, and cannot be opened from the report. Only the count leaks, never the content.

## Notes
Identical behaviour on every supported series (14.0 – 19.0). Follower rows without a partner (the channel followers that existed in 14.0) are excluded, since they do not notify a person.

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
