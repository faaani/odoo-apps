# User Login Report

Odoo shows a "Latest authentication" date on the user form and nothing else, so answering *who actually uses this system?* means writing SQL against `res_users_log`. This module adds a read-only report listing every user with the real last login, how many days ago it was, and a clear flag for accounts that have **never** logged in.

## Features
- Real last login per user — the latest login record, not any login record.
- Days since last login: a searchable, sortable column.
- Never Logged In flag for accounts that were created and never used.
- Login status: Never / Active (last 30 days) / Idle (30-90 days) / Dormant (90+ days).
- Filters: never logged in, dormant 30/60/90+ days, active in the last 30 days, internal vs portal, enabled vs archived accounts.
- Multi-company safe: the same record rule Odoo applies to users, so the report never shows more than the Users list.
- Group by login status, user type or company; export the list to spreadsheet.
- One grouped SQL query, no per-user loop, and no writes: your data is never modified.

## Installation
1. Copy the module into your addons path (or install it from the Apps list).
2. Open Apps, remove the "Apps" filter, search for *User Login Report* and click Install.
3. Only the standard base module is required.

## Configuration
1. No configuration is needed.
2. The report is restricted to users in the Administration / Settings group.
3. Optional: add the menu to your favourites for quick access.

## Usage
1. Go to Settings &rarr; Users &amp; Companies &rarr; User Login Report.
2. The list opens on internal users, sorted by the longest time without a login.
3. Use the filters (Never Logged In, Dormant 90+ Days, Active last 30 days, Portal / Public Users, Archived Accounts) or type a number in "Days since login (at least)".
4. Group by Login Status to count how many accounts are active, idle, dormant or never used.
5. Select all and use Export to produce a spreadsheet for your licence or security review.

## Notes
"Dormant" means the account logged in once and then went quiet; accounts that were never used have their own filter and their own status, so the two counts never overlap. The report never shows a user that the standard Users list would hide: it ships the same multi-company record rule Odoo applies to users. The OdooBot / superuser system account is excluded from the report. Identical behavior on every supported series (14.0 – 19.0).

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
