# -*- coding: utf-8 -*-
# Part of config_change_audit. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'System Parameter Audit Trail',
    'version': '15.0.1.0.0',
    'summary': 'Log every system parameter change — old value, new value, who and when — with secret masking and a retention cron.',
    'description': """
System parameters silently control half of Odoo's behaviour: the base URL, mail
size limits, feature switches, integration endpoints. Nothing in Odoo records
who changed one, when, or what the value used to be — the row is simply
overwritten and the previous value is gone.

This module records every system parameter that is created, changed or deleted:
the key, the old value, the new value, the author and the timestamp. The trail
is an admin-only list with filters by parameter, by author, by operation and by
date, and a retention setting with a daily clean-up.

Values of keys that look like credentials (key, secret, token, password) are
stored masked, so the audit trail never becomes a second place where your API
keys are readable. Very long values are stored truncated and flagged as such.

Audit logging can never break a configuration change: every hook is wrapped in
a savepoint and a try/except, and a failure is logged to the server log only.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'views/config_change_audit_views.xml',
        'views/res_config_settings_views.xml',
        'data/ir_cron_data.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
