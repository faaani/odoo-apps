# -*- coding: utf-8 -*-
# Part of record_last_update_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Stale Records Report',
    'version': '17.0.1.0.0',
    'summary': 'Find the records nobody has touched: counts by age and the oldest records of any model, with their last writer.',
    'description': """
Data quality rots quietly. Leads nobody touched in a year, contacts last edited
in 2019, products untouched since the import: nothing warns you, and Odoo has
no screen that answers "what has not been touched lately?".

This module adds a read-only report you point at any model:

* pick the model, an age in days and (optionally) an extra filter,
* get how many records are older than 30, 90, 180 and 365 days,
* get the oldest records listed with their last-update date and last writer,
* open any of them in one click, or open the whole selection as a list.

The counts come from aggregate queries and the sample list from one capped
search, so the table itself is never read row by row - only the handful of rows
you asked to see. Everything runs with your own access rights, so record rules
apply and the report can never show you a record you could not open yourself.

It is strictly read-only: it never writes to, archives or deletes the records it
reports on - it only ever stores your own report parameters. If you
want to act on what it finds, the companion module "Automatic Archiving Rules"
(auto_archive_stale_records) archives records on a schedule; it is a separate,
optional install and this module does not depend on it.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'security/stale_records_security.xml',
        'wizard/stale_records_wizard_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
