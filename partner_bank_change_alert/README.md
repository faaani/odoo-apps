# Partner Bank Change Alert

Every bank detail change: audited, masked, notified.

Changed-bank-detail invoice fraud is the classic accounts-payable scam: someone
edits a vendor's bank account and the next payment quietly goes to the wrong
hands. Out of the box, Odoo keeps no visible trail of that edit and warns
nobody. This module posts an audit message on the partner's chatter for every
added, modified or removed bank account and notifies a configurable alert
group the moment it happens.

Free and open source (LGPL-3), Odoo 14.0 through 19.0.

## Features

- **Full audit trail on the chatter** - who changed what, and when, for every
  create, edit and deletion of a `res.partner.bank` record.
- **Account numbers always masked** - only the last 4 characters are ever
  shown (`****1234`), old and new value alike; numbers of 4 characters or
  fewer are masked entirely.
- **Instant notification** - a configurable alert group (accounting managers
  by default) is notified on every change, without spamming the partner's
  other followers (the message is an internal note).
- **Repointing is a red flag** - moving a bank account to another partner
  alerts BOTH the old and the new partner's chatter.
- **Trust switch audited** - flipping the "Send Money" flag (trusted /
  untrusted for outgoing payments, Odoo 16.0+) is alerted too.
- **Never blocks business** - alerts are best-effort: a failed post is logged
  at ERROR level but the bank operation always goes through.
- **Multi-company aware** - group members are only notified about bank
  accounts of companies they belong to; company-less accounts notify the
  whole group.
- **Lightweight** - depends only on standard modules (`mail`, `base_setup`);
  works with or without the accounting app.

## Installation

1. Open **Apps**, search for *Partner Bank Change Alert* and click
   **Install**.
2. Only standard modules (`mail`, `base_setup`) are required. Alerts are
   active immediately with sensible defaults.

## Configuration

1. Go to **Settings > General Settings** and find the **Partner Bank
   Accounts** block.
2. Toggle **Bank Account Change Alerts** on or off (on by default).
3. Pick the **Alert Group** to notify. Empty means the default: the
   accounting managers when the accounting app is installed, otherwise the
   Settings administrators.

## Usage

1. Add, edit, move or delete any partner bank account, from any screen.
2. An internal note appears on the affected partner's chatter with the
   action, the masked number(s), the author and the timestamp.
3. Members of the alert group are notified (inbox or email, per their own
   notification preference).
4. Only meaningful fields trigger an alert: account number, holder name,
   bank and partner. Cosmetic edits (e.g. display sequence) stay silent.

## Honest limitations

- The audit trail lives in Odoo's chatter - someone with direct database
  access can still edit data below Odoo's radar.
- Notifications are best-effort by design and never block the underlying
  operation; a failed alert is logged at ERROR level in the server log.
- This complements - it does not replace - the untrusted-account payment
  flagging that Odoo 16+ accounting applies at payment time. Odoo 14 and 15
  have no such flagging, which is exactly where this module helps most.

## Support

Questions, bugs or feature requests: **f.ashraf.dev1@gmail.com**

License: LGPL-3.
