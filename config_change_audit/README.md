# System Parameter Audit Trail

System parameters silently control half of Odoo's behaviour: the base URL, mail size limits, feature switches, integration endpoints. Nothing in Odoo records who changed one, when, or what the value used to be — the row is simply overwritten and the previous value is gone.

This module records every system parameter that is **created, changed or deleted**, with the key, the old value, the new value, the author and the timestamp.

## Features
- One row per real change, for create, write and delete — including changes made through `set_param()` by other modules and by the Settings pages.
- Old value **and** new value, side by side.
- The author and the exact time of the change.
- Renamed keys keep their previous key.
- **Secret masking**: parameters whose key contains `key`, `secret`, `token` or `password` (configurable) are stored as `********` in both the old and the new value. The real value is never copied into the audit table.
- **Long values are truncated** to their first 512 characters and the row is flagged `Truncated`, so a certificate or a JSON blob does not get duplicated into the trail.
- Admin-only list with filters by parameter, author, operation (created / updated / deleted), date (today, last 7 days, last 30 days), masked keys and renamed keys; group by parameter, operation, author or date; export to spreadsheet with Odoo's standard export permission.
- **Retention**: a daily scheduled action deletes rows older than the configured number of days (365 by default, 0 keeps them for ever).
- **Auditing can never break a configuration change.** Every hook runs inside a savepoint and a `try/except`: if the audit write fails, the failure goes to the server log and the parameter change still succeeds.
- Rows can not be created, edited or deleted by anyone — the access rules grant read access only, so an administrator can not forge, back-date or remove an entry either. The module writes rows itself and the retention clean-up is the only thing that removes them.

## Installation
1. Copy the module into your addons path, or install it from the Apps list.
2. Open Apps, remove the "Apps" filter, search for *System Parameter Audit Trail* and click Install.
3. Only the standard `base_setup` module is required.

## Configuration
1. Go to Settings &rarr; General Settings &rarr; **System Parameters**.
2. **System Parameter Audit Trail** — tick to record changes (on by default).
3. **Keep History (days)** — how long rows are kept; a daily scheduled action removes older ones. Set 0 to keep them for ever.
4. **Mask Keys Containing** — comma-separated, case-insensitive fragments; default `key,secret,token,password`. Leave empty to mask nothing.
5. Changes to these three settings are always recorded, even while auditing is switched off, so the trail can not be turned off silently.

## Usage
1. Open the trail with the **Open the audit trail** button on the Settings page, or from Settings &rarr; Technical &rarr; Parameters &rarr; **System Parameter Audit Trail** (the Technical menu requires developer mode).
2. The list shows the most recent change first: date, parameter, operation, old value, new value and author.
3. Filter by Created / Updated / Deleted, by Today / Last 7 Days / Last 30 Days, by *Masked (Secret) Keys* or *Renamed Keys*; or type a parameter name in the search box.
4. Group by Parameter to see the whole history of one setting, or by Changed By to see what one administrator changed.
5. Open a row to read long values in full, and select-and-export for a security review (exporting needs Odoo's standard "Allow Export" permission).

## What is and is not covered
- Only **system parameters** (`ir.config_parameter`, the *System Parameters* list) are audited. Company fields, user preferences and other models are not.
- Changes made **before** the module was installed can not be shown — nothing recorded them.
- Masked values are stored as `********`: the trail proves that a secret changed and who changed it, never what it was changed to.
- Values longer than 512 characters are stored cut down to their first 512 characters, and the row says so.
- The author is the user who made the change, including when a module writes the parameter with `sudo()` on their behalf. Changes made by scheduled actions, by the command line or during a module installation are recorded as OdooBot, since no user is behind them; when code genuinely runs as OdooBot inside a web request, the logged-in user of that request is recorded instead.
- The list is restricted to the Administration / Settings group.

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
