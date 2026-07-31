# Email Bounce Report

Odoo counts bounces per contact, and its own Discuss code drops a contact from a channel
once that counter reaches 10 — but it never shows you *who* is bouncing. This module adds the
missing screen, and changes nothing at all.

## The problem

Every contact carries a **Bounce** counter (`res.partner.message_bounce`). Odoo increments
it when an address bounces and resets it when that address answers again. Odoo's own Discuss
code treats **10** bounces as the point where an address is dead and unsubscribes the contact
from the channel. Core `mail` does not otherwise stop sending to it.

That counter is buried on the contact form, one contact at a time. There is no list, no
filter and no total — so a mailing list decays invisibly.

## What this module adds

* A read-only **Email Bounce Report** listing every contact that has a bounce counter above
  zero *or* sits on the email blacklist.
* The contact, the exact address stored on it, and the normalized address Odoo actually
  matches against the blacklist.
* The standard bounce counter, plus an **Above Threshold** flag using an inclusive `>=`
  test against a threshold you set in Settings (default **10**).
* The date of the most recent message to that contact that is recorded as bounced, and how
  many such messages survive.
* Whether the address is on the **active** email blacklist, and when it was put there —
  with a button that opens the blacklist entry.
* Filters for bounced at all, at or above threshold, below threshold, blacklisted, not
  blacklisted, with or without an address, active or archived contacts.
* Group by company, country, blacklist status, threshold status or bounce month, and export
  with the standard Odoo export.

## This module never changes anything

It owns no data of its own. The report is a single read-only database view over information
Odoo already stores, so:

* it **never edits a contact** and never resets a bounce counter;
* it **never adds or removes a blacklist entry**, and never opts anyone in or out of a
  mailing;
* it **never sends, retries or cancels** an email;
* it only links out — to the contact, and to the blacklist entry.

The report model is granted read access only, to Settings / Administration users, so even
an administrator cannot write through it.

## Honest limitations

* **There is no true "bounce timestamp" in Odoo, on any supported series.** Odoo records the
  bounce on the message notification, and that model (`mail.notification`) is declared
  without access logging, so it carries no date at all. The *Last Bounced Message* column
  therefore shows the date of the *message* that bounced — not the moment the bounce came
  back. Nothing is invented: when no bounced message survives, the column is simply empty.
* The *Bounced Messages* count can be lower than the bounce counter. Odoo garbage-collects
  old notifications, and the counter is shared by every record carrying the same address.
* The bounce counter itself is maintained by Odoo, not by this module. If your incoming mail
  server is not configured to route bounces back into Odoo, the counter stays at zero and so
  does this report.
* Contacts with no email address are listed if they carry a bounce counter (an address can
  be cleared after the fact) and are flagged accordingly. They can never match a blacklist
  entry.
* The report mirrors Odoo's own record rules on contacts — the multi-company rule on every
  series, plus the private-address rules on 14.0–16.0, where employees' home addresses are
  walled off from internal users outside the *Access to Private Addresses* group. It will
  never show a contact that the standard Contacts list would hide from that user.
* Only bounces recorded against a **contact record** are counted. On 19.0 Odoo can also
  record a bounce against a bare address with no contact behind it (mass mailing); those are
  not counted in *Bounced Messages* or *Last Bounced Message*. The *Bounces* counter itself is
  unaffected, because Odoo maintains it per contact.
* The report reads live data every time you open it, so it is always current and there is no
  cache or scheduled job to go stale — but it aggregates the bounce notifications on every
  read. On a database with millions of message notifications, opening it can take a few
  seconds.

## Installation

1. Copy the `mail_bounce_report` folder into your Odoo add-ons path.
2. Log in as an administrator and turn on developer mode
   (*Settings → General Settings → Developer Tools*).
3. Open *Apps*, click *Update Apps List*, then search for **Email Bounce Report** and press
   *Install*.
4. The only dependency is Odoo's standard *Discuss* (`mail`) module.

## Configuration

1. Go to *Settings → General Settings* and find the **Email Bounces** section.
2. Set **Bounce Threshold** to the number of bounces at which you want a contact flagged.
   The test is **inclusive**: a contact with exactly that many bounces *is* flagged.
3. The default is **10**, the same limit Odoo's own Discuss code uses before it considers an
   address dead.
4. Press *Save*. The report picks the new threshold up immediately — no upgrade, no reload.
5. Changing the threshold changes the report only. It never changes a contact and never
   changes who Odoo mails.

## Usage

1. Open *Settings → Technical → Discuss → Email Bounce Report* (developer mode shows the
   Technical menu).
2. The list opens on every contact that is bouncing or blacklisted, worst first. Clean
   contacts are not listed at all.
3. Apply **At or Above Threshold** to see only the addresses worth acting on, or
   **Blacklisted** / **Not Blacklisted** to see which dead addresses are still being mailed.
4. Type a number into the *Bounces (at least)* search field for an ad-hoc cut-off without
   touching the configured threshold.
5. Group by **Company** or **Country** to find a whole segment that is decaying, and use the
   standard export to hand the list to whoever cleans it.
6. Open a line and use *Open Contact* or *Open Blacklist Entry* to act on it. Any correction
   you make happens there, on the real record — deliberately, not as a side effect of
   running a report.

## Support

* Email: f.ashraf.dev1@gmail.com
* Source and issues: https://github.com/faaani/odoo-apps

Author: Farhan Ashraf · Licence: LGPL-3 · Supported: Odoo 14.0, 15.0, 16.0, 17.0, 18.0, 19.0
