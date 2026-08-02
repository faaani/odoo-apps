# -*- coding: utf-8 -*-
# Part of partner_private_address_type. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Private Address Type for Contacts',
    'version': '15.0.1.0.0',
    'summary': 'Group-gate the Private address type on contacts: a visible security group, record rules and a search filter for private addresses.',
    'description': """
Through Odoo 16.0 contacts have a "Private Address" type, but the access
separation around it hides behind a technical group that is hard to
discover and manage.

This module makes that separation explicit: it adds a visible security
group, "See Private Addresses" (membership also grants the core
private-address access group), record rules hiding private addresses
from internal users outside the group, and a group-gated search filter.
Normal contacts, companies, portal and public users are unaffected.

A safety constraint prevents marking a partner as private while it is
linked to an active user, which would otherwise break that user's login
and profile.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/security.xml',
        'views/res_partner_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
