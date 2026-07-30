# -*- coding: utf-8 -*-
# Part of database_size_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Database Size Report',
    'version': '18.0.1.0.0',
    'summary': 'See which tables use your database: size, indexes, estimated rows and the Odoo model behind each one.',
    'description': """
When an Odoo database starts filling the disk, nothing in the interface says
what is responsible. Answering it normally means opening psql and knowing the
right catalog query.

This module adds a read-only report for administrators:

* the size of the whole database on disk, at the top,
* every table with its size, its index size and the total it really costs,
* the Odoo model stored in each table, resolved from the registry (so
  ir_act_window is correctly shown as ir.actions.act_window),
* an estimated row count taken from PostgreSQL's own statistics, so the report
  is instant even on a database of hundreds of gigabytes,
* tables sorted biggest first, with each table's share of the total,
* a plain-language note on the tables that are usually responsible:
  mail_message and mail_tracking_value (chatter), mail_notification and
  mail_followers, ir_attachment, ir_logging and the various *_log tables.

Tables that belong to no Odoo model - the relation tables behind many2many
fields, for instance - are listed too, with an empty model.

The figures are read from the PostgreSQL catalog with fixed queries that take no
user input at all: none of your tables is scanned, no row is counted one by one,
and not a single business record is read, changed or deleted. The only thing the
module writes is the report you are looking at, a temporary record Odoo cleans up
on its own. It never deletes anything else and never offers to. Access is
restricted to Settings administrators, because the sizes cover the whole database.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/database_size_report_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
