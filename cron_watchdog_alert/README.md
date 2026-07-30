# Cron Watchdog Alerts

Scheduled actions fail silently: the queue stalls, a worker dies, an action
gets disabled — and you find out days later when invoices were never mailed.
This module emails administrators as soon as any scheduled action is overdue
beyond a configurable lag. Free, LGPL-3, Odoo 14.0 – 19.0.

## Installation
1. Install from **Apps** (search "Cron Watchdog Alerts").
2. Standard `mail` and `web` modules only. Active immediately with sensible
   defaults (60-minute lag, one alert per action per 24 h).

## Configuration
Optional System Parameters (Settings → Technical → System Parameters):
- `cron_watchdog_alert.enabled` — `False` disables all alerting (default on).
- `cron_watchdog_alert.lag_minutes` — how overdue an action must be before it
  counts as stalled (default 60, minimum 15 to avoid noise from a busy queue).
Per-action: open a Scheduled Action → **Watchdog** section → tick
**Exclude from Watchdog** for jobs you don't care about.

## Usage
- A watchdog job checks every 30 minutes; overdue actions trigger one email to
  all Settings administrators (sent immediately, not queued — the mail queue
  itself may be the thing that is down).
- A lightweight, throttled check also runs on normal backend page loads, so
  **even a fully dead cron worker is caught** while people keep using Odoo.
- Each stalled action re-alerts at most once per 24 hours; the last alert time
  is visible on the action's form.

## Honest limits
If the cron worker is dead AND nobody opens Odoo, no in-Odoo mechanism can
alert you — pair this with an external uptime check if you need that guarantee.

## Notes per version
Identical behavior on all supported series (14.0 – 19.0).

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
