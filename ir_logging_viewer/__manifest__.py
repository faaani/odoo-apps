# -*- coding: utf-8 -*-
# Part of ir_logging_viewer. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Server Log Viewer',
    'version': '16.0.1.0.0',
    'summary': 'Read the log entries Odoo stores in the database - filter by level, logger, date and message text, with a retention cleanup.',
    'description': """
When something goes wrong, administrators end up opening an SSH session just to
read a log. Odoo can already write its log records into the database table
``ir_logging``, but the only screen for it is a raw list hidden in the Technical
menu with no level filter, no date range and no way to keep the table from
growing.

This module turns that table into a usable screen: quick filters for errors,
warnings, info and debug, filters by logger name and date, free-text search
inside the message, grouping by level or logger, a shortened message column in
the list and the complete message and traceback in the form.

It also adds a retention window with a daily cleanup so the table cannot grow
without bound, and a confirmed "clear entries" wizard.

Important: this screen shows only what Odoo persists to the database. Odoo does
that when the server runs with the ``log_db`` option; it is not a viewer for the
server log file.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'wizard/ir_logging_clear_wizard_views.xml',
        'views/ir_logging_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
