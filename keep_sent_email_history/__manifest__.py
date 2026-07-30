# -*- coding: utf-8 -*-
# Part of keep_sent_email_history. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Keep Sent Email History',
    'version': '15.0.1.0.1',
    'summary': 'Stop Odoo from deleting sent emails — keep a full, auditable outgoing email history with configurable retention.',
    'description': """
Odoo deletes most notification and template emails from the queue right after
sending, so Settings > Technical > Emails stays empty and you can never audit
what was actually emailed, to whom, and when.

This module keeps every sent email, with a configurable retention period and a
daily cleanup job so your database does not grow forever.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Discuss',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/mail_mail_views.xml',
        'data/ir_cron_data.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
