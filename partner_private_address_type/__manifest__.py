# -*- coding: utf-8 -*-
# Part of partner_private_address_type. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Private Address Type for Contacts',
    'version': '17.0.1.0.0',
    'summary': 'Restore the Private address type removed in Odoo 17 and hide private addresses from users outside a dedicated security group.',
    'description': """
Odoo 17 removed the "Private Address" type that contacts had through 16.0,
so sensitive personal addresses lost their separation on upgrade.

This module restores the Private Address type on contacts and adds a
dedicated security group, "See Private Addresses". Internal users outside
the group cannot read, write or delete partners whose address type is
private; members of the group and administrators see them normally.
Normal contacts, companies, portal and public users are unaffected.

A safety constraint prevents marking a partner as private while it is
linked to an active user, which would otherwise break that user's login
and profile.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/security.xml',
        'views/res_partner_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
