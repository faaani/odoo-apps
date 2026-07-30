# Retry Failed Emails in Bulk

After an SMTP outage, hundreds of messages sit in the Odoo mail queue in **Delivery
Failed** state. Standard Odoo can only cure them one at a time: open the message, click
Retry, go back, open the next one.

This module adds an administrator screen that lists the failed messages with their
subject, recipient, age and the exact error the mail server returned, and acts on them in
bulk.

Free and open source (LGPL-3), Odoo 14.0 through 19.0.

## Features

- See what failed and why: subject, recipient, age in days and the first line of the SMTP
  error, oldest first.
- Retry the messages you tick. Nothing is pre-selected when the whole queue is loaded, so
  nothing goes out by accident.
- Retry everything queued on or after a date you choose, including messages that are not
  listed on screen.
- Cancel the messages that must never be sent. They are left in Cancelled state, never
  deleted.
- An honest report after every run: re-queued, delivered, failed again immediately, left
  in the queue, removed from the queue by Odoo, cancelled, skipped and errors. A message
  Odoo deleted while processing it (they are flagged "auto-delete") is reported on its own
  line and never counted as delivered — Odoo removes those whether the server accepted the
  message or refused the address, so the queue can no longer tell you which.
- One bad recipient address cannot abort the batch: every message is processed inside its
  own database savepoint.
- Uses Odoo's own Retry and Send code path, not hand-rolled SMTP.
- Also available from **Settings > Technical > Email > Emails**: select messages and use
  **Action > Retry / Cancel Failed Emails**.

## The warning the module puts on its own screen

Retrying an old message delivers it today. A message that failed a week ago is sent
unchanged, and its recipient receives it now — with a week-old date, price or link
inside. Check the age column before you retry, and cancel whatever should never go out.

## What is never touched

- **Sent** messages: re-sending would deliver a duplicate to your customer.
- **Outgoing** (pending) messages: the standard mail queue cron is already going to send
  them.
- **Cancelled** messages: somebody decided they must never leave, and this screen never
  resurrects them. Use the standard Retry button on the message itself if you change your
  mind.

Only messages in Delivery Failed state are listed and modified. Nothing is ever deleted.

## Installation

1. Open **Apps**, remove the default "Apps" filter if needed, and search for *Retry Failed
   Emails in Bulk*.
2. Click **Install**. Only the standard `mail` module is required.
3. No configuration is needed: the screen appears immediately under Settings.

## Configuration

1. There is nothing to configure. Access is restricted to users with Settings /
   Administration rights (`base.group_system`), which is also who can read the mail queue
   in standard Odoo.
2. Fix the cause first: **Settings > General Settings > Discuss / Emails** for the
   outgoing mail server. Retrying while the server is still down simply fails again — and
   the result panel says so.
3. Optional: leave *Send immediately* unticked to only put messages back in the queue and
   let the standard "Email Queue Manager" scheduled action deliver them.

## Usage

1. Open **Settings > Retry Failed Emails**. The screen lists the failed messages, oldest
   first, with the total waiting.
2. Tick the messages you want (or use *Tick All Listed*), then click **Retry Selected**
   and confirm.
3. Alternatively fill *Retry From Date* and click **Retry Since Date**: every failed
   message queued on or after that date is retried, including messages not shown on
   screen. This works on the whole queue, so it is offered only when the screen was
   opened from the Settings menu — never when you arrived from a selection.
4. Use **Cancel Selected** for messages that should never be sent.
5. Read the result panel: re-queued, delivered, failed again immediately, left in the
   queue, removed by Odoo, cancelled, skipped and errors. *Refresh List* reloads what is
   still failing — with a selection larger than one page, it loads the next messages of
   your selection.
6. From **Settings > Technical > Email > Emails** you can also select messages and use
   **Action > Retry / Cancel Failed Emails**.

## Limits, stated honestly

- The list shows the 300 oldest failed messages at a time, and says so on screen when
  there are more. Use *Retry Since Date* to cover the rest.
- One *Retry Since Date* run re-queues at most 1000 messages, and tells you when it
  stopped there so you can run it again. A selection larger than 1000 is cut to the first
  1000, and the screen says how many were left out.
- *Send immediately* delivers at most 50 messages per run inside the request; the rest are
  re-queued for the standard mail cron. Messages are sent one at a time — that costs one
  connection to your mail server each, but it means a message the server has already
  accepted can never be rolled back and sent twice. For large batches, leave the option
  unticked and let the mail cron deliver them in a single connection.
- A message flagged "auto-delete" (most notification emails) is deleted by Odoo as soon as
  it has been processed, so this screen cannot report whether it was delivered. Those are
  counted separately as *Removed From Queue*; the outcome is on the document the message
  came from.
- Odoo does not store the moment a message failed, so the date filter and the age column
  use the date the message was queued — the closest reliable timestamp.
- Sending obeys your configured outgoing mail server. This module does not diagnose or
  repair SMTP settings; it only reports what the server answered.

## Version notes

Identical behaviour on every supported series (14.0 - 19.0); only the view markup differs
internally (`attrs` up to 16.0, `list` instead of `tree` on 18.0 and 19.0).

## Support

Questions, bugs or feature requests: **f.ashraf.dev1@gmail.com** — I read and answer every
message.

License: LGPL-3.
