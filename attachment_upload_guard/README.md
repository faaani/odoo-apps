# Attachment Upload Guard

Odoo lets anyone attach anything, of any size — executables, scripts and half-gigabyte videos land in your database and every backup you take. This module adds the upload policy Odoo does not ship: a blocked file-type list and a maximum size, enforced wherever users attach files, including the chatter and Discuss.

## Installation
1. Open Apps, search for Attachment Upload Guard and click Install.
2. Only standard base_setup is required. Sensible defaults apply immediately.

## Configuration
1. Go to Settings &rarr; General Settings and find the Attachments block.
2. Adjust Blocked File Types (comma-separated, e.g. exe,bat,msi) — leave empty to allow every type.
3. Set Maximum Size (MB), or 0 for no size limit, then Save.

## Usage
1. A user attaching a blocked or oversized file gets a clear error and the upload is refused.
2. Existing attachments are untouched; the policy applies to new uploads and to later edits.
3. To allow a one-off upload, temporarily adjust the policy in Settings.

## Notes
Identical behavior on every supported series (14.0 – 19.0).

Free, LGPL-3, Odoo 14.0 – 19.0.
