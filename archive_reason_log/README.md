# Archive with a Reason

Archiving hides a record from everyone with one click, and Odoo keeps no trace of
*why*. This module adds **Archive with Reason** to the Action menu: pick the
records, choose a reason from a list you configure, add an explanation when the
reason asks for one, and the reason is stored on each record, posted once in its
chatter and written to a searchable log.

Supported series: **14.0, 15.0, 16.0, 17.0, 18.0, 19.0**. License: **LGPL-3**.
Only depends on `mail`.

## Features

* Reason list you control: order, per-model restriction, and an explanation
  policy per reason (*optional*, *required*, *not allowed*).
* Exactly one chatter note per archived record, carrying the reason and the
  free-text explanation.
* **Archive Log** report: record, model, reason, explanation, author, date and
  status - filterable and groupable by reason, model, author, status and month.
* Restoring a record clears the reason from the record and marks its log entry
  *Restored* with the date and the user; the history row is kept. The log is the
  source of truth: it closes correctly even if the record's own reason column was
  cleared by an import or a script.
* Per-record savepoint: one record that refuses to archive never aborts the
  batch, and the result reports how many failed and the first error.
* Up to 500 records per run. Beyond that the wizard refuses with a clear message
  and archives nothing, rather than timing out halfway through.

## What is never touched

* `res.users`, `res.company` and every technical `ir.*` model are refused
  outright - the wizard does not even open on them.
* In a contact selection, the contact of a user and the contact of a company are
  excluded automatically; the dialog says how many records were skipped.
* Models without an *Archived* flag, or without a chatter, are refused with a
  message naming which of the two is missing.
* Records that are already archived are skipped, not re-archived.
* Nothing is ever deleted; only the standard `active` flag is set to false.

## Relation to `archive_audit_trail`

`archive_audit_trail` (also free) posts a short chatter note on *every* archive
and restore, wherever it happens, with no reason and no configuration. This
module is the deliberate path: it asks for a reason and produces a report, but
only for archives done through its own dialog.

They are meant to live together. When both are installed, an archive made
through this wizard posts **one** note - the detailed one - because this module
suppresses the plain note for that single write. Archives made anywhere else are
still logged by `archive_audit_trail` exactly as before. Neither module requires
the other.

## Installation

1. Copy the module into your addons path and update the Apps list.
2. Open **Apps**, search for *Archive with a Reason* and click **Install**.
3. Only the standard `mail` module is required.

## Configuration

1. Go to **Settings > Archived Records > Archive Reasons** (Settings
   administrators only).
2. Five reasons are installed to get you started; edit, reorder or replace them.
3. Per reason, set **Free-text Explanation** to *Optional*, *Required* or *Not
   allowed*, and optionally a short **Guidance** line shown in the dialog.
4. Use **Limit to Models** if a reason only makes sense on some models; leave it
   empty to offer it everywhere.
5. At install, the Action-menu entry is added to every installed model that has
   an *Archived* flag and a chatter. After installing new apps, run **Settings >
   Archived Records > Update Action Menus** once so the new models get it too.

## Usage

1. Open any list (Contacts, Products, Employees...) and tick the records.
2. Choose **Action > Archive with Reason**.
3. Pick a reason, type the explanation if the reason asks for one, press
   **Archive**.
4. Read the confirmation: archived, skipped, failed.
5. Open **Settings > Archived Records > Archive Log** for the history, or the
   record's chatter to read the reason in place.
6. Restore the usual way (Action > Unarchive): the reason is cleared from the
   record and the log entry becomes *Restored*.

## Good to know / limitations

* Only archives made **through this dialog** carry a reason and appear in the
  log. The standard Archive button records nothing here, by design.
* Two plain text columns (`archive_reason`, `archive_reason_note`) are added to
  every model that has a chatter. They are text on purpose: a relational field
  would add a foreign key to each of those tables, and PostgreSQL validates a
  new foreign key with a full table scan under an exclusive lock - a nasty
  surprise on a large `account_move` or `sale_order`. The columns are not
  injected into any existing form view; add them yourself if you want the reason
  on a form. The relational history lives in the Archive Log.
* The chatter note is best effort. If it cannot be posted - most often because
  the user's own account has no email address, which stops any Odoo chatter
  post - the record is still archived and logged, and the result says how many
  notes were missed.
* The Action-menu entry is created per model at install time, and removed again
  when the module is uninstalled; models that arrive later need the one-click
  *Update Action Menus*. The entry is offered to all internal users, but Odoo's
  own access rights still apply: archiving a record you cannot write is refused,
  reported per record, and never blocks the rest of the batch.
* The Archive Log and the reason list are for Settings administrators. Ordinary
  users can archive with a reason and read their own log entries; they cannot
  create, edit or delete log rows by any other route. Settings administrators
  can delete log rows - the module does not try to make history immutable.
* The log keeps the record name as it was at archive time, so the history stays
  readable if the record is later renamed or deleted. That means archiving
  contacts copies personal names into a second table; worth knowing if you have
  a data-retention policy.

## Support

Questions, bugs or feature requests: **f.ashraf.dev1@gmail.com**
