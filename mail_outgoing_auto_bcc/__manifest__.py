# -*- coding: utf-8 -*-
# Part of mail_outgoing_auto_bcc. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Auto CC / BCC on Outgoing Emails',
    'version': '17.0.1.0.0',
    'summary': 'Send an automatic CC or BCC copy of every outgoing email - compliance and archiving made simple.',
    'description': """
Many companies must keep a copy of every email that leaves the system:
compliance archives, a shared "sent" mailbox, a CRM auto-logger.
Odoo has no built-in way to do that.

This module adds two fields to General Settings - Auto CC and Auto BCC,
comma-separated address lists per company. Every email sent through Odoo's
outgoing mail queue (chatter notifications, templates, the composer,
scheduled mail) is delivered with those addresses added as CC / BCC.
Addresses already present among the recipients are never duplicated,
and an empty configuration adds zero overhead.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail', 'base_setup'],
    'data': ['views/res_config_settings_views.xml'],
    'uninstall_hook': 'uninstall_hook',
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
