# Failed Email Alerts

When SMTP credentials expire, a relay starts rejecting recipients or the mail
server simply goes down, Odoo does not complain: messages quietly pile up in the
outgoing queue in *Delivery Failed* state. Nobody notices until a customer asks
why the invoice never arrived.

This module watches the outgoing mail queue and emails the Settings
administrators a summary — subjects, recipients and the first error returned by
the mail server — as soon as too many messages have been stuck for too long.
Free, LGPL-3, supported on Odoo 14.0 – 19.0.

## Installation
1. Install the module from **Apps** (search "Failed Email Alerts").
2. No extra dependencies — only `base_setup` and `mail` from standard Odoo.

## Configuration
1. Open **Settings → General Settings** and scroll to the **Emails** section
   (it is called **Discuss** on Odoo 14.0 – 17.0).
2. **Failed Email Alerts** is enabled by default; untick it to silence the
   watchdog on this database.
3. **Alert Above (emails)** — how many stuck messages are needed before an alert
   goes out (default 5, values below 1 are treated as 1).
4. **Minimum Age (minutes)** — messages queued more recently than this
   are normal traffic and are not counted (default 60, floor 5).

## Usage
- A scheduled action ("Email: alert on a stuck outgoing queue") runs every
  4 hours and counts messages in *Outgoing* or *Delivery Failed* state that are
  older than the age window.
- Above the threshold, every user with Settings access and an email address
  receives one summary listing the 20 oldest stuck messages.
- The alert is **force-sent in-process** rather than queued: the mail queue is
  exactly what cannot be trusted at that moment.
- At most one alert is sent per 24 hours, however broken the mail server is.
- Alert messages are flagged (`Queue Alert Notice`) and never counted as
  evidence themselves, so a failing alert cannot feed itself.
- Full queue: **Settings → Technical → Email → Emails**.

## Notes per version
Identical behavior on all supported series (14.0 – 19.0); only settings-view
markup and the `ir.cron` fields differ internally.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
