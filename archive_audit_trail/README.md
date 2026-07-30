# Archive Audit Trail

"Where did that customer go?" Archiving hides a record from everyone in one click, and Odoo keeps no trace of who did it. This module posts a short note in the record's chatter every time it is archived or restored — the user and the moment, permanently.

## Installation
1. Open Apps, search for Archive Audit Trail and click Install.
2. Only the standard mail module is required.

## Configuration
1. None. Logging starts immediately.
2. To pause it, set the System Parameter archive_audit_trail.enabled to False.

## Usage
1. Archive any record (customer, product, employee, pricelist) from the Action menu or its form.
2. Open the record and read its chatter: a note names who archived it and when.
3. Restoring the record logs a matching note, so the full history stays in one place.

## Notes
Identical behavior on every supported series (14.0 – 19.0).

Free, LGPL-3, Odoo 14.0 – 19.0.
