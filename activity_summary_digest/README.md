# Daily Activity Digest Email

Odoo activities only nag you inside Odoo. Close the tab and the reminder is gone: calls, follow-ups and to-dos quietly slide past their due date because nothing reaches people where they actually look — their inbox.

This module sends every user who opted in one email each morning, listing the activities **assigned to them** that are **due today or already overdue**, grouped by document type (Contact, Task, Sales Order, ...), with overdue lines marked in red and every line linking straight to the record in Odoo.

Users who have nothing due are not emailed at all — there is no "you have 0 activities" message.

## Installation
1. Copy the `activity_summary_digest` folder into your addons path (or install it from the Apps store).
2. Open Apps, click Update Apps List, search for *Daily Activity Digest Email* and click Install.
3. No external Python library is needed. The module depends only on `mail` and `base_setup`, which every Odoo database already has.
4. Installing changes nothing on its own: the per-user preference starts switched off, so no email is sent until somebody opts in.

## Configuration
1. Make sure Odoo can send email: **Settings → Technical → Outgoing Mail Servers**. Without one, no digest can leave the system.
2. Go to **Settings → General Settings → Activities**. **Daily Activity Digest** is the master switch and is on after installation; turning it off silences every digest at once, whatever each user asked for.
3. Opt users in. Either each user ticks **Daily Activity Digest** themselves in their **Preferences** (avatar menu → My Profile), or an administrator opens **Settings → Users & Companies → Users →** a user **→ Activity Digest**, or clicks **Turn on for all internal users** under the settings switch to subscribe everybody in one go (confirmation dialog; active internal users only).
4. Check each user's **Timezone** and **Language** in Preferences: they decide which calendar day counts as "today" for that person, and which language and date format the email uses.
5. Choose the sending time. Enable developer mode, open **Settings → Technical → Scheduled Actions → Send daily activity digest emails** and set **Next Execution Date** to the moment of the first run — it repeats every 24 hours from there. The value is stored in UTC and shown in your own timezone.
6. Nothing else to configure: there is no template, no recipient list and no filter to maintain.

## Usage
1. Work normally: schedule activities on contacts, tasks, orders or any other document, as you already do.
2. Once a day the scheduled action builds one email per opted-in user who has something due, and sends it. Users with nothing due are skipped entirely.
3. Read the digest: a count at the top, then one block per document type. Red *Overdue* lines first inside each block, then the ones due today, each with its activity type, its summary and its due date.
4. Click the record name on any line to open that document in Odoo and deal with the activity there.
5. To test it without waiting for the morning, open the scheduled action and press **Run Manually** — every opted-in user with something due receives their digest immediately.
6. To stop receiving it, untick **Daily Activity Digest** in your own Preferences. To stop it for everyone, turn the switch off in General Settings.
7. If nobody receives anything, check in order: the global switch, the user's checkbox, whether the user really has an activity due today or overdue, whether the user has an email address, and the Odoo log for outgoing-mail errors.

## What this module never does
The digest is strictly read-only. It never creates, modifies, reschedules, completes or deletes an activity, and it never touches the documents behind them.

It never subscribes anyone by itself: the per-user checkbox starts at *off*, so installing the module sends nobody anything. The administrator button that opts everybody in is behind a confirmation dialog, is restricted to the Settings group, and only touches active internal users — a user who then unticks the box in their own preferences stays unsubscribed.

Portal, public and share users are never emailed, and neither are users without an email address. Activities are read **as the recipient**, so a document that user is not allowed to read never reaches their inbox.

## Limitations
**A working outgoing mail server is required.** The digest goes through Odoo's standard mail queue and is force-sent so it cannot sit there all day — but if no outgoing mail server is configured, or SMTP refuses the message, nothing arrives: the failure is written to the Odoo log and that day's digest is *not* retried later.

**It covers Odoo activities (`mail.activity`) and nothing else** — not calendar events as such, not project deadlines, not overdue invoices, not unread messages. Only activities whose assignee is the recipient are listed; an activity you scheduled for somebody else appears in *their* digest, not yours.

**Due today or earlier only.** Activities with a future deadline are deliberately never listed: this is a "what must I not forget today" email, not a preview of the week.

**One email per user per run**, and the scheduled action runs once a day, so a user who opts in at noon starts with the next morning's digest.

**Volume is capped** at the 100 oldest lines, taken from at most 500 activities. When the cap is hit the email says so and points back to Odoo, rather than mailing somebody a thousand-line table.

**The layout is fixed.** The email body is generated in Python, not from a `mail.template`, so restyling it means overriding `_activity_digest_mail_values()` rather than editing a template in the UI. Sent digests are auto-deleted like other Odoo notification mails, so there is no permanent archive of them.

**Odoo 15.0 and 16.0 only:** core itself hides an activity from its own assignee when that user does not hold write access on the underlying document (`_mail_post_access`). Such activities are invisible in Odoo's own activity views on those series too, and they are therefore also absent from the digest. Odoo 14.0 and 17.0–19.0 do not have that restriction.

"Due today" is computed from the recipient's **Timezone** in Preferences; a user who left it empty is treated as UTC, and an unknown timezone falls back to UTC with a warning in the log.

## Robustness
Each recipient is processed inside its own savepoint, so one broken user (bad email address, an exotic document model) is logged and skipped without costing everybody else their digest.

An activity whose record was deleted in the meantime — or which the recipient may no longer read — is skipped instead of raising, and the digest is only sent if at least one line survived.

Record links use the modern `/odoo/<model>/<id>` URL on 18.0 and 19.0 and the classic `/web#id=...` hash before that, so they open correctly on every supported series.

The scheduled action runs as OdooBot, repeats indefinitely, and does not catch up on missed runs — a server that was down overnight sends the next digest at the next scheduled time rather than several at once.

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
