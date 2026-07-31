# Check Attachment Files

A database restored without its filestore, a half-finished migration, a backup that only covered PostgreSQL: the rows in `ir.attachment` survive, the files behind them do not. Odoo says nothing about it — the damage surfaces months later, when somebody clicks Download and gets an error.

This module adds an administrator scan that walks the filestore-backed attachments, checks that each file really exists, and reports what was lost: grouped by model, with the record, the owner, the upload date, the size and the exact filestore path that could not be read.

Optionally it also compares each file's size with the size recorded in the database, and — as an opt-in, because it reads every byte — recomputes each file's SHA1 to catch a file that was corrupted without changing size.

## Installation
1. Copy the `attachment_link_checker` folder into your addons path (or install it from the Apps store).
2. Open Apps, click Update Apps List, search for Check Attachment Files and click Install.
3. No external Python library and no other module is required — it only depends on `base`.

## Configuration
1. There is nothing to configure. The scan works on the attachments already in your database.
2. Access is limited to the Settings group (Administration: Settings). Give that group to anyone who should be able to run the scan.
3. Run the scan as a user who has access to every app. Odoo hides attachments whose linked record belongs to a model the user may not read; the report tells you how many were hidden (Hidden From You), and that number should be zero.
4. The scan reads the filestore of the machine it runs on. On a multi-server setup, run it on a server that has the filestore mounted, or the files will look missing when they are not.
5. In multi-company databases only the companies currently selected in the company switcher are examined.

## Usage
1. Go to Settings &rarr; Attachment Files &rarr; Check Attachment Files. The scan runs immediately with the default options.
2. Read the summary: how many attachments were examined, how many were checked on disk, how many are broken, and how much content was lost.
3. Open the Broken Attachments tab for the detail — model, record, file name, problem, uploader, date, size and the path the file should be at. Use Attachment or Record on a row to jump straight to it.
4. Use the By Model tab to see which models were hit hardest.
5. To go deeper, tick Verify Checksums and click Check Files again. This reads every byte of every file, so it is slow on a large filestore, but it is the only way to catch a file that was corrupted without changing size.
6. Narrow the scan with Limit to Model, Uploaded From/Until or Include Field Attachments, and control the cost with Batch Size, Stop After and Broken Rows to List.
7. Restore your filestore and run the scan again — the recovered files disappear from the report by themselves.
8. Only if the files are gone for good: tick Delete on the rows you want to drop and click Delete Ticked Records. A confirmation dialog appears, the disk is checked once more, and only the ticked dangling records are removed.

## What this module never does
It never deletes an attachment on its own. The scan itself never reads, writes or deletes a file — with checksum verification off it does not open a single one, and with it on it only reads. A missing file is usually recoverable: restoring the filestore brings it straight back, and a scan that had deleted the database rows would have thrown that recovery away.

The optional cleanup exists for the case where the files are gone for good. It only removes rows you ticked, after an explicit confirmation; it refuses any row whose file is still on disk; it re-checks the disk immediately before deleting, so a restore that happened since the report can never be undone by a stale list; it refuses rows that are the value of a binary field on a record (a logo, a photo, a stored report); and it deletes with your own access rights rather than as superuser. Failures on one row do not abort the rest.

Even the cleanup removes no file content: deleting an attachment makes Odoo core enqueue its (already missing) filestore entry for the standard garbage collector, which writes a zero-byte marker under `filestore/checklist/`. Core's collector skips any file still referenced by another attachment, so a de-duplicated file shared by several attachments is safe.

## Limitations
Only attachments backed by the filestore can be checked on disk. Attachments stored inside the database (`db_datas`) and link/URL attachments hold no file, so they are counted separately and excluded from the disk check — they appear in the summary so the numbers always add up.

The scan resolves paths through Odoo's own `ir.attachment._full_path()`, so it follows a custom filestore location; if a third-party module stores attachment content somewhere else entirely (S3 and similar), that content is outside what this module can verify.

Checksum verification needs a checksum stored on the attachment. Rows that have none are reported as "No Stored Checksum" instead of being silently passed. Size comparison is skipped for rows whose recorded size is zero.

**The scan only sees what your user is allowed to see.** Odoo removes from every attachment search the attachments whose linked record belongs to a model the current user has no access to — so a Settings administrator who does not also hold the Accounting or HR groups would never be shown a broken invoice PDF. Rather than leave that gap silent, every report counts the attachments it was not allowed to examine and says so, in the summary (**Hidden From You**) and in the result note. Run the scan as a user with access to every app to bring that number to zero. This is also why access is restricted to the Settings group: the report exposes filestore paths and file names across the whole database.

## Performance
The attachment table is read a page at a time (`Batch Size`, default 500) and file contents are never loaded into memory unless checksum verification is switched on — and then only 512 KB at a time. The number of pages the scan read is shown on the report. Identical files share one filestore file, so each distinct path is inspected once.

With `Verify Checksums` on, the scan reads every byte of the filestore inside a single web request. On a very large filestore combine it with `Stop After` so the scan cannot outlast the server's request timeout and lose its result.

Identical features and identical results on every supported series (14.0 – 19.0). The number of pages reported is a property of the ORM's paging on each series and is not comparable between them.

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
