# Find Duplicate Attachments

The same quotation PDF gets emailed, re-attached and re-uploaded dozens of times, and Odoo keeps every copy as its own attachment. This module groups attachments by the checksum Odoo already stores and shows every group of identical files: how many copies exist, the space the redundant copies account for, and where the copies are attached. Clean-up is a second, explicitly confirmed step that keeps the oldest copy of every group and removes only the extras.

## Two scopes
- **Same record only (default)** — a group is the same file attached several times to the same record. Removing the extras can never leave a record without its file.
- **Anywhere in the database** — identical files wherever they are. Only one copy survives for the whole database, so records whose own copy is removed keep no link to the file. The wizard says so before you confirm.

## What is never reported and never deleted
- Attachments that store a binary field of a record (`res_field` is set) — deleting one would empty that field on the record.
- Attachments of the framework models `ir.ui.view`, `ir.asset`, `ir.actions.report` and `ir.module.module` — the asset bundles and the module plumbing Odoo keeps for itself.
- Empty files: there is nothing to reclaim, and a zero-byte row is usually evidence of a failed upload.
- Unique files. A file is only ever touched when another copy of the exact same bytes exists inside the same group, and only after the oldest copy of that group has been secured.
- Anything you untick, and everything at all until you tick the confirmation box.

Two things to know before deleting: a copy that was posted in a chatter message disappears from that message as well, and a link built on an attachment id — an image pasted into an email template, a website page or a description — breaks if that particular copy is the one removed. The default same-record scope is the conservative choice for both.

## Installation
1. Copy the `duplicate_attachment_cleaner` folder into your addons path.
2. Open Apps, click Update Apps List, search for Find Duplicate Attachments and click Install.
3. No dependency beyond the standard base module.

## Configuration
1. Nothing to configure. Access is granted to the Settings / Administration group only.
2. Choose the scope: Same record only (default) or Anywhere in the database.
3. Optional: raise "Ignore Files Smaller Than (KB)" to skip small icons and signatures.
4. Optional: change "Groups To List" if you want more or fewer groups on screen (1000 at most); the totals always cover the whole database.
5. Take a backup before your first clean-up, as you would for any bulk deletion.

## Usage
1. Go to Settings &rarr; Attachments &rarr; Find Duplicate Attachments.
2. Pick the scope, then click Scan for Duplicates. The result is a report: no attachment is modified.
3. Read the groups: file name, number of copies, redundant space, where the copies belong and the date of the oldest copy.
4. Untick any group you want to keep as it is.
5. Click "Clean Up Ticked Groups...", check the numbers, tick the confirmation box and click Delete Extra Copies.
6. The oldest copy of every ticked group stays, the extras are deleted, and the scan is refreshed with a summary. Groups you may not write, or that changed during the run, are left alone and reported.

## Good to know
Odoo stores one physical file per checksum in the filestore, so the immediate win is a smaller attachment table, shorter attachment lists and lighter database dumps; disk space is reclaimed for attachments stored in the database and once the filestore garbage collector has run. Deletions go through the standard attachment access rules.

## Notes
Identical behavior on every supported series (14.0 – 19.0).

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
