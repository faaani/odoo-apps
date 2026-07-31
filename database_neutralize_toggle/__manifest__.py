# -*- coding: utf-8 -*-
# Part of database_neutralize_toggle. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Sandbox Mode - Database Neutralize Toggle',
    'version': '16.0.1.0.0',
    'summary': 'Reversible one-click neutralize: switch off every mail server and scheduled action on a restored copy, with a warning banner.',
    'description': """
A production database restored for testing keeps sending real emails and
running live scheduled actions until someone remembers to switch them off.
Odoo's own "neutralize" is a command-line tool, only exists on 16.0 and
later, and cannot be undone.

This module adds a single Sandbox Mode toggle in General Settings. Turning
it on snapshots and deactivates every outgoing mail server, incoming mail
server and scheduled action, and shows a fixed red "SANDBOX MODE" banner in
the web client. Turning it off restores the exact previous active flags -
servers or crons that were already disabled before stay disabled.

Limitations, stated plainly: it deactivates ALL scheduled actions with no
exceptions; it cannot block mail sent through a local sendmail binary when
no outgoing server record is used; it does not touch payment providers,
webhooks or any other outbound integration.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base_setup', 'web'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/webclient_templates.xml',
    ],
    'images': ['static/description/banner.png'],
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
