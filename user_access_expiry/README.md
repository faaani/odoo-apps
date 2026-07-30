# User Access Expiry Date

Set an end date on any user account. A daily job archives accounts whose date
has passed — contractors, interns, auditors and temporary staff lose access on
schedule instead of whenever someone remembers. Free, LGPL-3, Odoo 14.0 – 19.0.

## Installation
1. Install from **Apps** (search "User Access Expiry Date").
2. Only standard Odoo modules (`base_setup`, `mail`) are required.

## Configuration
No setup needed — setting a date on a user is the whole configuration.
Optionally, in **Settings → General Settings → Users** section, toggle
**Notify on Access Expiry** to control the administrator email summary
(on by default).

## Usage
1. Open a user (**Settings → Users**), go to the **Access Expiry** tab and set
   the **Access Expiry Date** (e.g. a contractor's end date).
2. The daily scheduled action "Users: deactivate expired accounts" archives the
   account once the date passes; the tab then shows **Deactivated by Expiry**
   and the exact timestamp.
3. Administrators (Settings access), OdooBot and the superuser are never
   archived, even with a past date.
4. Re-activating an archived user clears the audit flags and the stale date, so
   they are not re-archived the next night.
5. Filter users with **Has Expiry Date** or **Deactivated by Expiry** on the
   users list.

## Notes per version
Identical behavior on all supported series (14.0 – 19.0); only view markup
differs internally.
