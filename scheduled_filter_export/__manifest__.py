# -*- coding: utf-8 -*-
# Part of scheduled_filter_export. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Scheduled Export by Email',
    'version': '16.0.1.0.0',
    'summary': 'Send a filtered list of any model by email on a schedule: pick the model, the filter, the columns, the day - a CSV or Excel file is mailed automatically.',
    'description': """
Every business has someone who opens the same list every Monday morning,
exports it and mails it to a colleague. It is five minutes of clicking, it is
forgotten whenever that person is on holiday, and Odoo has no built-in way to
automate it.

This module adds **Scheduled Exports**: choose a model, an optional filter, the
columns you want, a schedule (daily, weekly or monthly) and the people who
should receive the file. An hourly scheduled action builds the file and emails
it as an attachment.

Key points:

* CSV always; Excel (XLSX) when the ``xlsxwriter`` library is available on the
  server. If it is not, the file is sent as CSV and the email says so instead
  of the export failing.
* Every export runs **as a chosen user**, so Odoo's record rules apply to that
  person: the recipients receive exactly the rows that user is allowed to see.
  An export never runs as the superuser, and only a Settings administrator may
  point one at somebody other than themselves.
* Exports are configured by users in the Administration / Access Rights group,
  because picking a model and its columns means reading Odoo's technical field
  list.
* Values are rendered for humans: many2one fields show the record name,
  selection fields show the label, dates and times use the language and
  timezone of the user the export runs as.
* Exports are capped at a fixed number of rows, and a truncated file says so on
  its last line as well as in the email.
* An export that matches no record sends no email at all - the run is recorded
  and logged, so nobody gets a daily empty file.
* Each export runs in its own savepoint: one broken export never stops the
  others.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/scheduled_export_security.xml',
        'views/scheduled_export_views.xml',
        'data/ir_cron_data.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
