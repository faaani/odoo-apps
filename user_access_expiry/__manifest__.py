# -*- coding: utf-8 -*-
# Part of user_access_expiry. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'User Access Expiry Date',
    'version': '18.0.1.0.1',
    'summary': 'Set an end date on any user — contractors and temporary accounts are archived automatically when it passes.',
    'description': """
Give any user an access expiry date. A daily job archives accounts whose date
has passed — contractors, interns, auditors and temporary staff lose access on
schedule instead of whenever someone remembers to deactivate them.

Full audit trail, administrator email summary, and hard safety guards:
administrators and OdooBot are never touched.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base_setup', 'mail'],
    'data': [
        'views/res_users_views.xml',
        'views/res_config_settings_views.xml',
        'data/ir_cron_data.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
