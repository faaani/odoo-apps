# -*- coding: utf-8 -*-
# Part of login_history_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'User Login Report',
    'version': '17.0.1.0.0',
    'summary': 'Report of every user with last login, days since last login and a flag for accounts that never logged in.',
    'description': """
Odoo shows a "Latest authentication" date on the user form and nothing else, so
answering "who actually uses this system?" means writing SQL against
res_users_log.

This module adds a read-only report listing every user with:

* the real last login (the latest login record, not any login record),
* how many days ago that was,
* a clear flag for accounts that have NEVER logged in.

Ready-made filters: never logged in, dormant for 30/60/90+ days, active in the
last 30 days, internal vs portal, enabled vs archived accounts. Group by login
status, user type or company, and export the list to spreadsheet.

The report is a single grouped SQL query (one row per user) - no per-user loop,
no writes: nothing in your database is modified. Visible to Settings /
Administration users only.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'security/login_history_report_rules.xml',
        'views/login_history_report_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
