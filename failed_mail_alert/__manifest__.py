# -*- coding: utf-8 -*-
# Part of failed_mail_alert. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Failed Email Alerts',
    'version': '16.0.1.0.0',
    'summary': 'Get warned by email when outgoing messages stop being delivered and pile up in the Odoo mail queue.',
    'description': """
When SMTP credentials expire, a relay starts rejecting recipients or the mail
server goes down, Odoo does not complain: it simply parks every message in the
outgoing queue in "Delivery Failed" state. Nobody notices until a customer asks
why the invoice never arrived - often days later.

This module adds a watchdog over the outgoing mail queue. When more than a
configurable number of messages have been stuck for longer than a configurable
age, it emails the Settings administrators a summary of what is failing:
subjects, recipients and the first error reported by the mail server. The alert
is force-sent in-process, because the mail queue itself is what is broken, and
it is rate limited to at most one message per 24 hours so a broken relay cannot
turn into an inbox flood.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base_setup', 'mail'],
    'data': [
        'views/res_config_settings_views.xml',
        'data/ir_cron_data.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
