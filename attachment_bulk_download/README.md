# Download Attachments in Bulk

Odoo downloads files one at a time. Collecting the signed contracts of thirty customers means opening thirty forms and clicking thirty times. This module adds a **Download Attachments** entry to the Action menu: tick the records, check how many files and how many megabytes that represents, and download them all as a single ZIP.

- The dialog shows the number of files, the total size and the configured limit before anything is built.
- Every file is stored as `<record name>/<file name>`, so two records with the same `contract.pdf` both survive; two identical names on one record become `contract.pdf` and `contract (2).pdf`.
- The archive holds the same set of files Odoo itself would let that user download — attachments of records they may not read are left out instead of breaking the download. No attachment or record is ever read with elevated rights.
- A selection over the configured total (200 MB by default) is refused with a clear message, and so is a selection of more than 5000 records.
- A file whose stored blob is missing from the filestore is skipped and logged, never handed over as an empty document.
- The ZIP is served by a dedicated `auth='user'` controller that resolves the attachments again server-side, so ids coming from the browser can never widen the archive.
- Read-only: no attachment or record is ever modified, moved or deleted.

## Installation
1. Copy the `attachment_bulk_download` folder into your addons path.
2. Open Apps, click Update Apps List, search for Download Attachments in Bulk.
3. Click Install. Only the standard `base_setup` module is required.

## Configuration
1. Go to Settings > General Settings > Attachments and set **Bulk Download Limit (MB)**. The default is 200 MB; 0 removes the limit.
2. The action is available on Contacts immediately after installation.
3. To offer it on another model, open Settings > Technical > Actions > Window Actions (developer mode), find *Download Attachments* and set that model in its bindings.
4. Every internal user (Employee) may use the action; each user still only ever receives the files they are allowed to read.

## Usage
1. Open a list view and tick the records whose documents you need.
2. Choose Actions > Download Attachments.
3. Check the file count and total size in the dialog, then click **Download ZIP**.
4. The archive lands in your browser's downloads, named after the record for a single record and `attachments-<n>-records.zip` otherwise.

## Good to know
- Only files *attached* to a record are included — the ones listed in the record's Attachments/paperclip area. Images stored in a binary field (contact photo, product image, company logo) belong to the record itself and are not attachments; they are not in the archive. This is the same set of files Odoo's own Attachments list shows.
- Attachments of type *URL* have no stored content and are skipped.
- The archive is built in memory, which is why the size limit exists: peak usage is roughly twice the limit per download in progress. On a small server, or with many users downloading at once, lower it.
- A single download covers at most 5000 selected records.

## Notes
Identical behavior on every supported series (14.0 – 19.0).

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
