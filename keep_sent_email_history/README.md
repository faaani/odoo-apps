# Keep Sent Email History

Odoo deletes most notification and template emails from the mail queue right
after sending — **Settings → Technical → Emails stays empty** and you cannot
audit what was actually emailed, to whom, and when. This module keeps every
sent email, with a configurable retention period and a daily cleanup job so
the database does not grow forever. Free, LGPL-3, Odoo 14.0 – 19.0.

## Installation
1. Install from **Apps** (search "Keep Sent Email History").
2. Only the standard `mail` module is required. Keeping is **active immediately**
   after install with a 365-day retention.

## Configuration
1. Open **Settings → General Settings → Discuss** section and find
   **Keep Sent Email History**.
2. Keep the switch on (default) and set **Email Retention (days)** —
   kept emails older than this are deleted by a daily job. Set **0** to keep
   emails forever.
3. Click **Save**.

## Usage
- Sent emails now stay in **Settings → Technical → Emails** (developer mode),
  including chatter notifications and template emails that Odoo used to delete.
- Use the **Kept by Email History** filter to see exactly which emails this
  module preserved.
- The daily job "Emails: purge kept history past retention" enforces the
  retention period; emails you keep manually (auto-delete off) are never touched.
- Switching the feature off stops keeping new emails; already-kept emails remain
  until retention removes them.
- **Password reset and signup invitation emails are never kept** — their bodies
  contain one-time login links, so the module lets Odoo delete them as usual.
- The cleanup also removes kept emails that ended in a failed/cancelled state,
  so bounced mass emails cannot grow the database forever.

## Notes per version
Identical behavior on all supported series (14.0 – 19.0); only view markup
differs internally.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
