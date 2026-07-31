# -*- coding: utf-8 -*-
# Part of password_expiry_policy. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Password Expiry Policy',
    'version': '15.0.1.0.0',
    'summary': 'Force backend users to change their password every N days - the rotation rule ISO 27001 and SOC 2 audits ask for.',
    'description': """
Odoo records no password age and has no rotation rule, so an auditor asking
"how do you enforce a maximum password age?" has nothing to look at.

This module stores the date of every password change on the user, and once the
configured period has passed it sends the user to a change-password page before
letting them back into the backend.

Built to be safe first:

* Ships DISABLED. Nothing changes until an administrator turns it on.
* Minimum period of 7 days is enforced, so a mistyped value cannot expire
  everybody at once.
* The database administrator, OdooBot, portal/public users and any user you
  flag as exempt are never expired.
* Only ordinary page loads are redirected. XML-RPC, JSON-RPC, /web/session
  endpoints, assets, downloads, cron and the mail gateway are never touched.
* The login page, the logout endpoint and the change-password page itself stay
  reachable at all times, so an expired user can never be locked in a loop.
* Installing the module stamps every existing user with the install date, so
  nobody is retroactively expired.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base_setup', 'web'],
    'data': [
        'views/password_expiry_templates.xml',
        'views/res_users_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
