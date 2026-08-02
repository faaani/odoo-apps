# -*- coding: utf-8 -*-
# Part of followers_audit_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Followers Audit Report',
    'version': '15.0.1.0.0',
    'summary': 'Read-only audit of mail followers: who follows the most records, and which records notify the most people.',
    'description': """
Nobody knows why they get so many Odoo notifications. Follower subscriptions are
scattered across every model and Odoo offers no place to look at them as a whole.

This module adds two read-only reports built on mail.followers:

* Followers by Person - one line per contact and document type, with the number
  of records followed on that type and the total across all types. Splits
  internal users from plain contacts.
* Records by Follower Count - the records with the most followers, so the
  document that mails half the company is easy to spot.

Filters: internal users vs contacts, by document type, and a minimum-count
filter on both reports (ready-made 5/10/25/100 thresholds plus a free "at least"
input). Group by follower, document type or follower type, and export to
spreadsheet.

The aggregate is a grouped query over mail.followers, ranked and limited by the
database itself - no per-record loop, and no million-row result built in memory
just to show the top of it. Partner names, model labels and record names are
resolved in bulk.

Nothing is ever modified or deleted: no follower row, no record, no user. To
actually unsubscribe someone, the reports link straight to the record, where
Odoo's standard chatter Followers button does the job.

Restricted to Settings / Administration users (base.group_system), because
follower data spans every model in the database. Counts are taken from the
follower rows themselves, so a record your own access rights hide from you is
still counted - it is then shown as "Document #id", flagged as not readable,
and cannot be opened from the report.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Productivity/Discuss',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/followers_audit_report_rules.xml',
        'views/followers_audit_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
