# Reassign Records in Bulk

When a salesperson or a project member leaves, every record they own has to be reassigned by hand, one form at a time. This module adds a **Reassign Owner** action: select the records — or simply pick *all records of user X* — choose the new owner, and apply.

- The responsible field is detected automatically on the active model — `user_id`, `user_ids` or `activity_user_id`, whichever the model stores and lets you edit; models without one give a clear message instead of an obscure error.
- "All records of a user" includes the leaver's archived records, so nothing is left behind.
- Access rights are respected: the reassignment runs as the current user, never with elevated privileges. Records you may not write are reported as skipped.
- A failure on one record never aborts the batch — each record is written in its own savepoint.
- Runs are capped at 10000 records: a bigger job processes the first 10000, reports exactly how many records are left, and a repeat run continues where it stopped. The cap keeps one run inside the worker time limit, so partial progress is never rolled back.
- A note is logged in the chatter of every record that changed.
- A summary tells you how many records were reassigned, how many were already assigned, skipped or failed.

## Installation
1. Open Apps, search for Reassign Records in Bulk and click Install.
2. Only the standard mail module is required.

## Configuration
1. None. The action is available immediately on Contacts; a technical user can bind it to any other model with a responsible field via Settings &rarr; Technical &rarr; Actions &rarr; Window Actions, by adding the model to the action bindings.

## Usage
1. Open a list view and tick the records to hand over.
2. Choose Actions &rarr; Reassign Owner in the toolbar.
3. Keep *Selected records*, or switch to *All records of a user* and pick the person who is leaving — the counter shows how many records are concerned.
4. Choose the new owner and click Reassign. The summary reports what changed.

## Notes
On a many2many responsible field the new owner is added and the previous owner removed, so the other collaborators are kept. Identical behavior on every supported series (14.0 – 19.0).

At most 10000 records are reassigned per run. When more records match, the summary says how many are left; simply run the action again until it reports nothing remaining.

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
