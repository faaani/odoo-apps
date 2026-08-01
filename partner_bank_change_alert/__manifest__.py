# -*- coding: utf-8 -*-
# Part of partner_bank_change_alert. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Partner Bank Change Alert',
    'version': '19.0.1.0.0',
    'summary': 'Chatter audit trail and instant notification when a partner bank account is added, changed or removed - the classic invoice-fraud blind spot.',
    'description': """
Changed-bank-detail invoice fraud is the classic accounts-payable scam: an
attacker edits a vendor's bank account and the next payment goes to them.
Odoo keeps no visible trail of that edit and warns nobody.

This module posts an audit message on the partner's chatter for every added,
modified or removed bank account - who did it, when, and the account number
masked to its last 4 characters - and notifies a configurable alert group
(accounting managers by default) so the change is seen the moment it happens.

Alerts are best-effort by design: a failure to notify is logged loudly but
never blocks the underlying operation.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Accounting',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base_setup', 'mail'],
    'data': ['views/res_config_settings_views.xml'],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
