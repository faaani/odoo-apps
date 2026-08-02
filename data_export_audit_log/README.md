# Export Audit Log

Audit trail of data exports: who exported which records, from which model,
with which fields, and when.

Export rights in Odoo are all-or-nothing, and once a user has the "Allow
Export" group there is zero trace of what left the database. This module logs
every export made through Odoo's standard export path (the list-view export
dialog, CSV and XLSX downloads - anything that calls `Model.export_data`).

## Features

- One log entry per export: user, model (technical name and label), record
  count, exact exported field list, timestamp. Odoo internally exports
  grouped lists group by group and very large lists in batches; those chunks
  are coalesced into a single entry, so the record count is the real total.
- Read-only list under **Settings > Export Audit Log**, visible to
  Settings / Administration users only, with filters (today, last 7/30 days,
  large exports) and group-by (user, model, date).
- Log rows cannot be created or edited from the UI or the ORM by anyone - they
  are written exclusively by the export hook - so the trail cannot be forged.
  Administrators may delete rows. The exporting user's login is stored on the
  row itself, so the trail survives even if the user record is later deleted.
- Daily scheduled action purges entries older than the configured retention
  (default 180 days; 0 keeps logs forever).
- Fail-safe: if writing the audit row fails, the export still succeeds and a
  warning goes to the server log. Logging never breaks exports.
- Superuser exports are logged too.

## Installation

1. Copy `data_export_audit_log` into your addons path.
2. Update the app list (developer mode: Apps > Update Apps List).
3. Install **Export Audit Log**.

## Configuration

1. Open **Settings > General Settings**, section **Export Audit**.
2. Set **Export Log Retention (days)** - default 180, 0 keeps logs forever.
3. Save.

## Usage

1. Any user exports records from a list view (Export button / dialog).
2. Open **Settings > Export Audit Log** (requires the
   Administration / Settings group) to review who exported what.
3. Filter by user or model, group by date, or delete entries you no longer
   need.

## Limitations (honest ones)

- Only exports going through the standard export path (`export_data`) are
  logged: the list-view export dialog and its CSV/XLSX downloads.
- Report PDF downloads, raw RPC/API reads (`search_read` etc.) and
  database-level dumps are NOT captured.
- Combine with a restrictive "Allow Export" group policy for real coverage of
  data leaving your system.

## Support

f.ashraf.dev1@gmail.com

License: LGPL-3.
