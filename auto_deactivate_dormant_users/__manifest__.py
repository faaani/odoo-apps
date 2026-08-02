# -*- coding: utf-8 -*-
# Part of auto_deactivate_dormant_users. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Auto Deactivate Dormant Users',
    'version': '19.0.1.0.2',
    'summary': 'Automatically archive users who have not logged in for N days - free seats, satisfy dormant-account security controls.',
    'description': """
Automatically deactivate (archive) internal users who have not logged in for a
configurable number of days. Frees paid seats and helps with dormant-account
requirements of ISO 27001 / SOC 2 audits.

Safe by default: disabled until you turn it on, never touches administrators,
OdooBot, portal users, or users you mark as exempt.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
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
