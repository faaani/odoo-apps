# -*- coding: utf-8 -*-
# Part of auth_login_lockout. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Login Attempt Throttling and Lockout',
    'version': '19.0.1.0.0',
    'summary': 'Lock a login out for a few minutes after repeated failed password attempts, record every attempt and alert administrators.',
    'description': """
Out of the box Odoo accepts an unlimited number of wrong passwords on the login
screen: an attacker can try a dictionary against a known e-mail address all day
and nothing slows them down, nothing is recorded, and nobody is told.

This module adds the missing brake.

* Every login attempt is recorded - the login used, the source IP, the result
  (successful, failed, or blocked while locked out).
* After a configurable number of failures for the same login (5 by default)
  that login is refused for a configurable number of minutes (15 by default),
  even if the correct password is supplied.
* The lockout is always time-based: every lockout expires on its own and
  knocking at a locked login does not extend the one already running. An
  attacker who keeps trying can still trigger a fresh lockout each time one
  lapses, so any administrator can release a lockout immediately.
* A successful login clears the counter.
* Unknown logins are throttled exactly like real ones, so the login screen
  cannot be used to find out which e-mail addresses are real accounts.
* Optional e-mail alert to every Settings administrator when a lockout starts
  for a real account. The attempt log records what was typed in the login box
  verbatim, so treat it as sensitive; it is restricted to administrators.
* Administrators can release a lockout immediately from the attempt list.
* A scheduled action purges attempts older than the retention period
  (30 days by default).

Everything is configured in Settings - General Settings - Login Security.
The attempt log lives in Settings - Users and Companies - Login Attempts and is
visible to Settings administrators only.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Extra Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base_setup', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/auth_login_attempt_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
