# -*- coding: utf-8 -*-
# Part of cron_watchdog_alert. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Cron Watchdog Alerts',
    'version': '14.0.1.0.1',
    'summary': 'Get an email the moment scheduled actions silently stop running - stale crons are found by a watchdog and on normal page loads.',
    'description': """
Scheduled actions fail silently: the queue stalls, a worker dies, an action
gets disabled - and you find out days later when invoices were never mailed.

This module watches every active scheduled action and emails administrators
as soon as one is overdue beyond a configurable lag. A lightweight check on
normal backend page loads catches even the case where the whole cron worker
is dead (as long as someone is using Odoo).
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base', 'mail', 'web'],
    'data': [
        'views/ir_cron_views.xml',
        'data/ir_cron_data.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
