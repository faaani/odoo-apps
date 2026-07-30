# Find Orphaned Attachments

Deleting a record does not always remove the files attached to it. After data imports, module uninstalls and failed jobs, attachments are left pointing at a record that is gone — or at a model that no longer exists at all — and they keep consuming filestore space forever.

This module adds a read-only scan that lists those orphaned attachments grouped by model, says why each group is orphaned, and shows how much space each group would give back. Deleting is a separate, explicitly confirmed action reserved for Settings administrators.

## Installation
1. Open Apps, search for Find Orphaned Attachments and click Install.
2. Only the standard base module is required.

## Configuration
1. None. The scan appears under Settings &rarr; Orphaned Attachments for users with Administration / Access Rights.
2. The delete button and its confirmation box are only shown to Settings administrators (Administration / Settings).

## Usage
1. Go to Settings &rarr; Orphaned Attachments. The scan runs immediately and only reads.
2. Review the lines: one per model, with the reason (the model no longer exists, or the record does not) and the reclaimable space.
3. Untick Delete on any group you want to keep.
4. Tick the confirmation box, click Delete Selected Attachments and confirm. Only the listed attachments are removed.
5. Click Rescan at any time to refresh the figures.

## Safety
Never listed and never deleted:
- attachments with no model at all — free-standing files users uploaded on their own;
- web assets and module data: `ir.ui.view`, `ir.asset`, `ir.actions.report`, `ir.module.module`;
- attachments with `res_field` set — the storage behind a binary field on a live record;
- attachments not linked to a record yet (upload in progress).

Archived records and records the current user cannot see are never mistaken for deleted ones: existence is checked directly against the table, ignoring record rules and the active flag.

## Notes
Identical behavior on every supported series (14.0 – 19.0).

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
