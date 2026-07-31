# Auto CC / BCC on Outgoing Emails

Send an automatic CC or BCC copy of every email Odoo sends - compliance and
archiving made simple.

Many companies must keep a copy of every email that leaves the system: a
compliance archive, a shared "sent" mailbox, a CRM auto-logger. Odoo has no
built-in way to do that. This module adds two fields to General Settings -
**Auto CC** and **Auto BCC** - and every email sent through Odoo's outgoing
mail queue is delivered with those addresses added.

## Features

- Covers everything the mail queue sends: chatter notifications, mail
  templates, the composer, scheduled and queued mail.
- Per-company: each company configures its own copy addresses.
- Comma-separated lists; blanks and invalid tokens are ignored.
- No duplicates: an address already among the recipients is never added twice
  (case-insensitive).
- Zero overhead when the settings are empty.
- Never blocks your mail: a bad configuration is logged and the email is sent
  unchanged.
- Security-aware: password reset and signup/invitation emails are never
  copied, so live login tokens cannot leak to the copy mailbox.

> **Treat the copy mailbox as privileged.** The Auto CC / BCC addresses
> receive a copy of your company's outgoing mail - quotations, invoices,
> private chatter replies. Only point them at mailboxes with appropriately
> restricted access.

## Installation

1. Install the module from the Apps menu (search for "Auto CC / BCC").
2. No extra dependency is needed beyond Odoo's standard Discuss (mail) app.

## Configuration

1. Open **Settings > General Settings** and find the **Automatic CC / BCC**
   setting in the email section.
2. Fill **Auto CC** and/or **Auto BCC** with comma-separated email addresses.
3. Save. In a multi-company database, switch company and repeat to configure
   each company.

## Usage

1. Send email as usual: post a chatter message, use a template, or let the
   queue flush.
2. The configured CC addresses appear in the Cc header of the delivered email.
3. The configured BCC addresses receive the email silently - the Bcc header is
   stripped before transmission, so other recipients never see them.
4. To stop copying, simply clear the fields and save.

## Honest limitations

- Applies to mail sent through Odoo's outgoing mail stack (the mail queue and
  direct sends). Mail sent by external systems on Odoo's behalf is not covered.
- BCC visibility depends on the receiving mail server; the copy is delivered
  as a separate envelope recipient.
- Emails sent before the module was configured are not retro-copied.
- The settings of the company of the user who created the email apply, also
  when the mail is flushed later by the queue cron; only mail sent outside
  Odoo's mail records falls back to the sending environment's company.
- Odoo sends one SMTP message per recipient batch, so the copy address
  receives one copy per outgoing SMTP message - an email with several
  recipients can arrive at the copy mailbox more than once.
- Password reset and signup/invitation emails are deliberately excluded from
  copying.
- The added addresses are applied at transmission time and are not stored on
  the email record in Odoo.

## Support

Questions, issues or ideas? Email f.ashraf.dev1@gmail.com - happy to help.
