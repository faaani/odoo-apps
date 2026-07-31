# Email Template Usage Report

See which email templates are actually used — and which ones nobody has touched
in years.

A database that has been live for a while ends up with dozens of email
templates, and nobody can tell which ones still matter. Odoo cannot tell you
either: core keeps **no link at all** between a sent email and the template that
produced it — neither `mail.mail` nor `mail.message` has a template field, on
any version from 14.0 to 19.0.

This module adds that link, records every send as it happens, and turns it into
a read-only report: one line per template, with how many emails it produced,
when it was last used, whether it was customised since installation, and whether
an automated action points at it.

Free and open source (LGPL-3), Odoo 14.0 through 19.0.

## What the report shows

* **Emails produced, first used, last used** — counted when the message is
  created, so the figures survive *Auto Delete*, which erases the evidence of
  the most heavily used templates seconds after sending.
* **Still stored** — how many outgoing mails and chatter messages produced from
  the template are still in the database, with buttons on the template's form to open
  them.
* **Where it came from** — shipped by a module (with the module name) or created
  in this database.
* **Customised since installation** — flagged when the template was edited after
  the module that ships it was last installed or upgraded. Those are the edits a
  cleanup would throw away.
* **Referenced by an action** — server actions, automated actions and activity
  types pointing at the template. That makes it *in use* even with zero recorded
  sends.
* **Ready-made filters** — Never Used, Used in the Last 90 Days, Not Used in 90+
  Days, Customized, Standard, In Use, Unused and Unreferenced, Referenced by an
  Action, Shipped by a Module, Created in this Database, Enabled, Archived.
  Group by usage, model, source, module, language or last used.
* **One query, whatever the size** — the report is a single SQL view with grouped
  sub-selects, never a query per template.

Depends on `mail` only. No cron, no scheduled job, no outgoing traffic, nothing
to configure.

## What this module never does

It never creates, edits, archives or deletes an email template, and it never
touches your emails. The report itself is a database view: create, write and
delete on it are refused, for administrators too.

The usage counters are written in raw SQL inside a savepoint, for two deliberate
reasons. First, a failure while recording statistics must never be the reason an
email fails to go out — if the update cannot be applied it is logged and the
send continues. Second, going through `write()` would move
`mail.template.write_date` on every single send and destroy the "customised
since installation" signal the whole report is built on.

The module adds two fields to your database: a read-only *Source Email Template*
link on `mail.mail` and on `mail.message`. Both are set to empty if the template
is later deleted; no existing field is modified.

## Honest limitations

* **Counting starts at installation.** Odoo stores nothing that ties an old
  email back to its template, so sends that happened before you install this
  module can never be counted — there is no history to recover. The *First Used*
  column tells you when tracking actually started to see each template.
* **"Never used" is not a permission to delete.** Templates are also called
  straight from Python code, from the Python part of server actions, and from
  configuration fields of other apps (stage-change emails, event registration,
  website and portal settings). Of those, only `ir.actions.server` and activity
  types are detected here. Always check a template before removing it.
* Send detection covers `mail.template.send_mail()` (and `send_mail_batch()` on
  17.0+), and the *Send Message* / mass-mail composer when a template is
  selected in it. A module that renders a template by hand and builds its own
  email is not detected, and Odoo's Email Marketing app sends from its own
  mailing records rather than from `mail.template`, so those campaigns are
  outside this report.
* The counters live on the template row: delete a template and recreate it and
  its history starts again from zero.
* The *Customized* flag compares the template's write date with the
  install/upgrade date of the module that ships it, so upgrading that module
  re-applies its own version of the template and clears the flag again; a
  template created in this database is custom by definition.
* Access is restricted to the **Settings** group because the report exposes
  every template in the database. Its menu sits under *Settings → Technical →
  Email*, and Odoo only shows the Technical menu in **developer mode**.
* On **14.0 and 15.0** the *Enabled* column is always ticked: `mail.template`
  only gained an *active* field in 16.0, so no template can be archived on those
  series.

## Installation

1. Copy the `mail_template_usage_report` folder into your addons path (or
   install it from the Apps store).
2. Open **Apps**, click **Update Apps List**, search for *Email Template Usage
   Report* and click **Install**.
3. No external Python library is required. The only dependency is `mail`, which
   every Odoo database already has.
4. Installation adds two columns (*Source Email Template* on `mail.mail` and
   `mail.message`) and creates the report view. Nothing else in your database is
   modified.

## Configuration

1. There is nothing to configure — recording starts with the next email sent
   from a template.
2. Access is limited to the **Settings** group (*Administration: Settings*).
   Give that group to anyone who should be able to open the report.
3. Turn on **developer mode** (Settings → General Settings → Developer Tools) so
   that the *Technical* menu appears; the report lives under **Settings →
   Technical → Email**, next to *Email Templates*.
4. Leave it running for a while before drawing conclusions. A template used once
   a year looks unused for eleven months — the *First Used* column tells you how
   long the report has actually been watching.

## Usage

1. Go to **Settings → Technical → Email → Email Template Usage**.
2. Read the list: **Emails Produced** and **Last Used** tell you what is alive,
   **Source** and **Customized** tell you what a module upgrade would overwrite,
   **Referenced** tells you what an automated action still needs.
3. Use **Group By → Usage** to split the templates into used recently, unused for
   90+ days and never used.
4. Apply **Unused and Unreferenced** to get the shortlist of templates worth
   reviewing, and **Customized** to find the local edits that an upgrade of the
   shipping module would silently replace.
5. Open a line to see the full picture, and use **Stored Emails** / **Stored
   Messages** to read what the template actually produced.
6. Optional columns — language, module, first used, auto delete, archived,
   server actions, activity types, stored counts — are available from the column
   picker at the top right of the list.
7. Before deleting anything: check the template's name in your own
   customisations and in the settings of your other apps. This report cannot see
   a template referenced from Python code.

## Version notes

The same features on every supported series (14.0 – 19.0). Two differences come
from Odoo itself: `mail.template` has no *active* field before 16.0, so the
*Enabled* column is always ticked on 14.0 and 15.0; and `send_mail_batch()` only
exists from 17.0, so only that entry point is hooked on 17.0 and later.

## Support

Questions, bugs or feature requests: **f.ashraf.dev1@gmail.com** — I read and
answer every message.

License: LGPL-3.
