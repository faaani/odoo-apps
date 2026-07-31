# Update a Field on Many Records

Changing a single field on three hundred records means three hundred clicks — or an export/import round trip that touches columns you never meant to touch. This module adds an **Update a Field** action to the list view: select the records, pick the field, enter the value, see how many records will really change, confirm, and apply.

## What it does

- Works on any model: the field list is built from the model you are looking at, and the input matches the field — text, number, date, checkbox, a dropdown for selection fields, a record picker for many2one fields.
- Previews the change: how many records will really change, how many already carry the value, how many you cannot see, how many were deleted meanwhile.
- Requires an explicit confirmation step showing the model, the field, its technical name, the value and the record count. The server refuses to apply a change that was not confirmed.
- Reports updated / skipped / failed, with the reason for each skip and the error of each failure, naming the records.
- Emptying a field is a separate tick box, never the consequence of an empty input. Required fields are refused.

## The guards

- Only writable fields are offered: read-only fields, computed fields Odoo does not let you edit, non-stored fields, related/delegated fields (they would write on another record than the one you selected) and the bookkeeping columns (`id`, `create_uid`, `create_date`, `write_uid`, `write_date`) are never listed.
- `active` is excluded on every model — archiving has its own, reversible tools.
- The user login, and any field whose name looks like a password, a secret, a token or an API key, is refused on every model.
- The field is validated again at apply time against the model and against your access rights, so a forged field name is refused rather than written.
- The model and the selected records are captured when the wizard opens and cannot be re-pointed afterwards. A record chosen as a many2one value must exist and be readable by you.
- The update runs as the current user, never with elevated privileges: records you may not see or may not write are skipped, named and counted.
- Every record is written in its own savepoint, so one failure never rolls back the batch.
- A note is logged in the chatter of each changed record, quoting the old and the new value, on models that have a chatter.
- The action is only visible to users with administrative (Settings) access.

## Installation
1. Open Apps, search for *Update a Field on Many Records* and click Install.
2. Only the standard `mail` module is required.

## Configuration
1. None. The action is available immediately on Contacts, for users with Settings access.
2. To offer it on another model, a technical user opens Settings → Technical → Actions → Window Actions, edits *Update a Field* and adds that model to the action bindings. The wizard itself already works on any model.

## Usage
1. Open a list view and tick the records to change.
2. Choose Actions → Update a Field.
3. Pick the field — only the ones you may write are listed.
4. Enter the value, or tick *Clear the value*. The counter tells you how many records will actually change.
5. Press Preview, check the confirmation screen, then Apply.
6. Read the report: updated, skipped and failed, with the reason for each.

## Limits
- Up to 10 000 records per run; beyond that the wizard refuses instead of silently truncating.
- Supported types: char, text, html, integer, float, monetary, boolean, date, datetime, selection, many2one. One2many/many2many, binary and company-dependent fields are not offered.
- Selection values produced by Python code (a language field, for instance) are typed in rather than picked from a dropdown; the allowed values are listed in the wizard and validated before the write.
- On Odoo 14.0 and 15.0 the many2one record picker also shows a model selector, which those clients cannot hide; pick the model named in the hint — anything else is refused.
- The chatter note quotes the old and the new value and is visible to everyone who can read the record, followers included — untick *Log a note in the chatter* when the value is sensitive.
- The update runs in one request, record by record: a batch of several thousand records keeps the dialog open for a while. There is no background job.
- The update is not undoable from the wizard; what changed is visible in the chatter of each record.

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
