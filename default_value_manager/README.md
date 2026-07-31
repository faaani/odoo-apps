# Manage Default Values

Somebody once used **Set Default** in developer mode. Odoo wrote a row in `ir.default` and never showed it again. Months later a field arrives pre-filled with a value nobody recognises, and there is no screen to look it up. This module adds that screen: every default value in your database, in readable form, with its scope — and a confirmed delete for the obsolete ones.

## Features
- Every default listed: model, field, technical name and label.
- The stored value rendered readable — `ir.default` keeps raw JSON; many2one ids become the target record's name, booleans become Yes/No, selections show their label, long values are shortened.
- The scope spelled out: all users or one named user, all companies or one named company, plus the optional condition.
- Obsolete entries flagged instead of crashing the list: *Orphaned* when the model or the field no longer exists, *Target record deleted* when the record it points at is gone, *Unreadable value* when the stored JSON cannot be parsed.
- Filter by model, field, user, company or status — or search on the readable value itself. Group by model, field, user or company, and export.
- Delete one entry with a confirmation, or several through the Action menu with a preview of exactly what goes.
- Add a default without developer mode: the field must exist on the model and the value must be convertible to its type; the entry is written through Odoo's own `ir.default.set()`.
- Restricted to the Administration / Settings group, and multi-company aware: an administrator restricted to some companies sees and deletes only those companies' defaults, plus the ones that apply to every company.

## Installation
1. Copy the module into your addons path (or install it from the Apps list).
2. Open Apps, remove the "Apps" filter, search for *Manage Default Values* and click Install.
3. Only the standard base module is required.

## Configuration
1. No configuration is needed.
2. The screen is restricted to users in the Administration / Settings group.
3. Multi-company: switch to the company whose defaults you want to manage; defaults that apply to every company are always visible.

## Usage
1. Go to Settings &rarr; Default Values &rarr; All Default Values.
2. Find the culprit: search on the model or field, or directly on the readable Value.
3. Open Obsolete Defaults for entries that can no longer work (orphaned model or field, deleted target record, unreadable value).
4. Delete one entry with the bin icon on its row, or tick several and choose "Delete Default Values" in the Action menu. Both confirm first.
5. To create a default, use Settings &rarr; Default Values &rarr; Set a Default Value: choose the model and field, type the value, choose the user and company scope.
6. Group by Model, Field, User or Company (Status is a filter, not a group), or export the list, for a configuration review.

## Notes
Deleting a default value only removes the pre-fill: records created earlier keep the value they were given, and no record, field or other setting is modified. The screen covers what Odoo stores in `ir.default`; defaults written in Python code (a field's `default=`) live in the source, not in the database, so they are not listed. The "Set a Default Value" screen accepts text, numbers, dates, booleans, selections and many2one fields — defaults on many2many, one2many, binary or reference fields are listed and can be deleted, but cannot be typed in there. Rendered values longer than 200 characters are shortened; the raw JSON is always available in its own column. Identical behavior on every supported series (14.0 – 19.0).

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
