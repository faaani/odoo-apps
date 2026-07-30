# Attachment Storage Report

When a database or filestore starts filling the disk, Odoo has no screen that answers the only question that matters: what is actually taking the space? This module adds a read-only storage report for administrators — attachments grouped by model and by uploading user, split between filestore and database, plus a list of the largest files and a minimum-size filter so the thousands of tiny records stop hiding the real offenders.

Every figure is aggregated by PostgreSQL, so the report stays fast on databases with hundreds of thousands of attachments.

## Installation
1. Copy the `attachment_storage_report` folder into your addons path (or install it from the Apps store).
2. Open Apps, click Update Apps List, search for Attachment Storage Report and click Install.
3. No external Python library and no other module is required — it only depends on `base`.

## Configuration
1. There is nothing to configure. The report works on the attachments already in your database.
2. Access is limited to the Settings group (Administration: Settings). Give that group to anyone who should be able to run the report.
3. In multi-company databases the report only counts the companies currently selected in the company switcher.

## Usage
1. Go to Settings &rarr; Attachment Storage &rarr; Storage Report. The report opens already computed.
2. Read the totals: how many attachments, how much space, and how it splits between the filestore and the database.
3. Use the By Model and By User tabs to find the biggest consumers, and the Open button on a row to jump to those attachments.
4. Raise Minimum Size (MB) (and optionally set an upload period), then click Run Report to recompute with the new filter.
5. Open the Largest Attachments tab to see the biggest files. Tick Delete on the ones you no longer need and click Delete Ticked Attachments; a confirmation dialog appears and only the ticked files are removed.

## Notes
The report is read-only. Nothing is ever deleted automatically, and the optional cleanup removes only the attachments you tick, after an explicit confirmation, using your own access rights. Files that are the value of a binary field (a logo, a photo, a stored PDF) are shown with their **Record Field** and the cleanup refuses them, so a record's image can never be erased by mistake.

The report aggregates the attachment table directly in SQL. It therefore reports on every attachment in the selected companies, including documents the administrator would not be able to open individually — which is why it is restricted to the Settings group.

Identical behavior on every supported series (14.0 – 19.0).

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
