# Scheduled Export by Email

Every business has that one person who opens the same list every Monday
morning, exports it and emails it to a colleague. Odoo has no built-in way to
automate it.

This module adds **Scheduled Exports**: pick a model, an optional filter, the
columns you want, a schedule (daily, weekly or monthly) and the recipients. An
hourly scheduled action builds the file and mails it as a CSV or Excel
attachment.

Free and open source (LGPL-3), Odoo 14.0 through 19.0.

## What it does

* **Any model, any filter** — contacts, sales orders, tasks, your own models.
  The filter is the standard Odoo domain editor.
* **The columns you choose, in the order you choose** — drag to reorder, and
  rename a column heading when the field label is not what the recipient
  expects.
* **Daily, weekly or monthly**, plus the hour the file should not go out
  before, read in the timezone of the user the export runs as. A "31st of the
  month" export still goes out in February.
* **CSV always, Excel (XLSX) when `xlsxwriter` is installed.** When it is not,
  the file is sent as CSV and the email says so rather than the export failing.
* **Readable values** — many2one columns show the record name, selection
  columns show the label, tags are joined by name, booleans read Yes/No, and
  dates use the language and timezone of the Run As user.

## It runs as a person, not as the system

Every export names a **Run As** user and reads the records with that person's
access rights and record rules — there is no `sudo()` anywhere on that path.
The recipients receive exactly the rows that user is allowed to see, and
nothing more.

An export can never run as the superuser, nor as a portal or archived account,
and only a Settings administrator may point an export at somebody other than
themselves.

## Built to be predictable

* New exports are **disabled** until you switch them on.
* A file holds at most **5000 rows**; a truncated file says so on its last line
  and in the email.
* An export that matches **no record sends no email at all** — the run is still
  recorded on the export as *No record matched*.
* Each export runs in its own savepoint: one broken export never stops the
  others, and its error is shown on the record.
* Text that a spreadsheet would run as a formula is neutralised before it
  reaches the recipient.

## Installation

1. Open **Apps**, search for *Scheduled Export by Email* and click **Install**.
2. Only the standard `base` and `mail` modules are required.
3. Installing creates one scheduled action, *Scheduled Export: send the exports
   that are due*, which runs every hour. It has nothing to do until you create
   an export and enable it.
4. For Excel files, make sure `xlsxwriter` is installed on the server
   (`pip install XlsxWriter`). It ships with most Odoo installations.
5. Check that outgoing email works (**Settings → Technical → Outgoing Mail
   Servers**) — the module hands the file to Odoo's normal mail queue.

## Configuration

1. The menu **Scheduled Exports** is visible to users in the *Administration →
   Access Rights* group. Choosing a model and its columns means reading Odoo's
   technical field list, which Odoo reserves to that group.
2. Click **New** and name the export, for example *Monday customer list*.
3. Pick the **Model**, then build a **Filter** with the domain editor. Leave it
   empty to export everything the Run As user can see.
4. On the **Columns** tab, add one line per column. Drag the handles to
   reorder; type a **Column Heading** to override the field label. File
   (binary) fields cannot be exported.
5. Choose the **Frequency** — every day, every week on a chosen weekday, or
   every month on a chosen day — and the hour the file should not go out
   before.
6. Set **Run As**. It defaults to you. Only a Settings administrator may choose
   somebody else.
7. On the **Recipients** tab, add the contacts who should receive the file, and
   any extra addresses that are not contacts in Odoo.
8. Pick the **File Format**: CSV or Excel (XLSX).

## Usage

1. Click **Preview Records** to open exactly the records the export currently
   matches. Nothing is sent, nothing is changed.
2. Click **Send Now** to build the file and email it immediately.
3. Happy with it? Switch **Enabled** on and the hourly scheduled action takes
   over.
4. **Last Run**, **Rows in Last File** and **Last Result** tell you what
   happened. A failed export shows its error and is retried on its next
   scheduled slot.
5. To pause an export, switch **Enabled** off; to retire it, archive or delete
   it.

## Good to know (limitations)

* The scheduled action runs **hourly**, so an export goes out at the first
  check at or after the hour you set — not to the minute.
* A file holds at most **5000 rows**; beyond that it is truncated, and the file
  and the email both say how many records matched in total.
* An export that matches no record sends no email. This is deliberate.
* **File (binary) fields cannot be exported.**
* The generated file is attached to the outgoing email and removed from Odoo
  once the email has been sent. It is not archived inside Odoo.
* In a multi-company database the export sees the companies allowed for the Run
  As user.
* Email is not encrypted end to end: anyone with access to a recipient's
  mailbox can read the file. Choose the Run As user and the recipients
  accordingly.

## Support

Questions, bugs or feature requests: **f.ashraf.dev1@gmail.com**

License: LGPL-3.
