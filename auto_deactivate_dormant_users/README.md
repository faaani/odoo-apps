# Auto Deactivate Dormant Users

Automatically archive internal users who have not logged in for a configurable
number of days. Frees paid seats and satisfies dormant-account requirements of
ISO 27001 / SOC 2 style audits. Free, LGPL-3, supported on Odoo 14.0 – 19.0.

## Installation
1. Install the module from **Apps** (search "Auto Deactivate Dormant Users").
2. No extra dependencies — only `base_setup` and `mail` from standard Odoo.

## Configuration
1. Open **Settings → General Settings**, scroll to the **Users** section and find **Auto Deactivate Dormant Users**.
2. Enable **Auto Deactivate Dormant Users** (disabled by default — nothing
   happens until you turn it on).
3. Set the **Dormancy Period** in days (default 90, minimum 7).
4. Optionally enable **Include Users Who Never Logged In** and
   **Notify Administrators**.

## Usage
- A daily scheduled action ("Users: deactivate dormant accounts") archives
  internal users whose latest login is older than the dormancy period.
- Never touched: administrators (Settings access), OdooBot, portal/share users,
  and users marked **Never Deactivate Automatically** (Dormancy tab on the user form).
- Archived users get **Deactivated by Dormancy** + date on the Dormancy tab;
  re-activating a user clears these flags automatically.
- Filter archived accounts via **Settings → Users → Filters → Deactivated by
  Dormancy** (enable the archived filter to see them).
- Administrators receive an email summary each time accounts are archived
  (if notifications are enabled).

## Notes per version
Identical behavior on all supported series (14.0 – 19.0); only view markup
differs internally.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
