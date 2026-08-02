# -*- coding: utf-8 -*-
# Part of cron_execution_history. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Scheduled Action History',
    'version': '19.0.1.0.0',
    'summary': 'Log every scheduled action run: start time, duration, success or failure and the error message, with retention and a daily cleanup.',
    'description': """
Odoo keeps no history of its scheduled actions. Did last night's job run at all?
How long did it take? Why did it fail? The only trace is the server log, if you
still have it.

This module records every run of every scheduled action:

* when it started and how long it took,
* whether it succeeded or failed,
* the error type, message and traceback when it failed.

The history is an administrator-only list, pivot and graph: runs per action,
average duration, failure count, grouped by action, result, error type or day,
with a link back to the scheduled action itself.

A failure record survives the failing job: the row is written on its own
database transaction, so it is still there after Odoo rolls the job back. The
recorder never interferes with the job - the exception is always re-raised
exactly as Odoo raised it, and a logging problem can never break a run.

The history cannot grow forever: a retention setting (30 days by default) and a
daily cleanup keep it bounded. Set the retention to 0 to keep everything.
Recording of successful runs can be switched off to keep failures only, and the
whole feature can be switched off from Settings.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base', 'base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'views/cron_execution_history_views.xml',
        'views/ir_cron_views.xml',
        'views/res_config_settings_views.xml',
        'data/ir_cron_data.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
