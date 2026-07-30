# Bulk Import Email Blacklist

Blacklist &mdash; or un-blacklist &mdash; hundreds of email addresses at once, from pasted
text or an uploaded CSV/TXT file, with a per-address report.

Odoo's *Email Blacklist* screen accepts one address at a time. After a bounce report, an
abuse complaint export or a GDPR erasure request, that means filling the same form over
and over. This module adds a bulk wizard.

## Features

* Paste addresses (one per line, or several per line separated by a comma or a semicolon),
  or upload a `.csv` / `.txt` file.
* Two modes: **Add to the blacklist** or **Remove from the blacklist**. Add is the default;
  remove asks for confirmation.
* Normalizes stray whitespace, mixed case and `Name <address@example.com>` forms, then
  writes through Odoo's own `mail.blacklist` helpers so the usual chatter entry is logged
  on every blacklist record.
* Per-address report: added, already blacklisted, removed, not blacklisted, listed more
  than once, invalid (with the reason for each one).
* Invalid entries are handed back as plain text, and one button reloads them into the
  wizard so only those need fixing.
* Each address is processed in its own database savepoint, so one bad row can never abort
  the run.
* Hard limit of 1,000 addresses per run; when the input is longer the wizard processes the
  first 1,000 and says on screen that it truncated.

## What it never does

* It never deletes a blacklist entry &mdash; "remove" archives it, which is Odoo's own
  un-blacklist behaviour.
* It never creates a blacklist row for an address you asked to remove that was not
  blacklisted; that address is reported as "not blacklisted".
* It never touches contacts, leads, mailing lists or anything else. Only `mail.blacklist`
  is written.
* It never bypasses access rights. The wizard is restricted to Settings administrators
  (`base.group_system`), the same group Odoo requires for the blacklist itself.

## Installation

1. Copy the `mail_blacklist_bulk_import` folder into your Odoo add-ons path.
2. Restart the Odoo service.
3. Open **Apps**, click **Update Apps List**, search for *Bulk Import Email Blacklist* and
   press **Install**.

The only dependency is `mail`.

## Configuration

1. Nothing to configure: the module works as soon as it is installed.
2. Access is limited to the **Settings** administrator group (`base.group_system`).
3. The menu sits next to Odoo's own blacklist screen, under **Settings > Technical >
   Discuss > Blacklist Bulk Import**. Odoo's whole Technical menu - including the standard
   *Blacklisted Email Addresses* screen - is only visible with **developer mode** enabled,
   so the same applies here.
4. If **Email Marketing** is installed, no developer mode is needed: open **Email
   Marketing > Configuration > Blacklisted Email Addresses**, tick any row and use
   **Actions > Bulk Import Email Blacklist**.

## Usage

1. Go to **Settings > Technical > Discuss > Blacklist Bulk Import**, or open **Blacklisted
   Email Addresses**, select any row and use **Actions > Bulk Import Email Blacklist**.
2. Choose the mode: *Add to the blacklist* or *Remove from the blacklist*.
3. Choose the source: paste the addresses, or switch to **Upload a file** and pick a
   `.csv` or `.txt` file. In a CSV the first cell of each row containing an `@` is used,
   and a leading header row called *email*, *e-mail* or *address* is ignored.
4. Press **Add to Blacklist** (or **Remove from Blacklist**, which confirms first).
5. Read the summary. If some entries were invalid, press **Fix Invalid Addresses** to
   reload only those, correct them and run again.
6. Press **View Blacklist** to check the result in the standard Odoo screen.

## Good to know

* An address is rejected when Odoo cannot normalize it, or when its domain has no dot
  (`user@localhost` is refused on purpose). The reason is printed next to the address.
* Addresses repeated inside one input are counted once and reported as "listed more than
  once"; they are not errors.
* Re-adding an address that was previously un-blacklisted reuses the existing archived
  record instead of creating a second row.
* CSV files with several columns are supported, but an address whose quoted display name
  contains a comma is best pasted as plain text.
* A run reads at most 1 MB of pasted text or uploaded file; anything larger is refused
  with a message rather than parsed.

## Compatibility

Odoo 14.0, 15.0, 16.0, 17.0, 18.0 and 19.0 &mdash; Community and Enterprise.

## Support

Questions, bug reports and feature requests: f.ashraf.dev1@gmail.com

Author: Farhan Ashraf &middot; https://github.com/faaani/odoo-apps &middot; Licence: LGPL-3
