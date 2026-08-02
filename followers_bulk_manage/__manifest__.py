# -*- coding: utf-8 -*-
# Part of followers_bulk_manage. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Manage Followers in Bulk',
    'version': '16.0.1.0.0',
    'summary': 'Add and remove followers on many records at once from the Action menu.',
    'description': """
Odoo adds or removes a follower one record at a time. Putting the new account
manager on ninety customers, or taking a departed colleague off every open
project, means opening ninety chatters.

This module adds "Manage Followers" to the Action menu: select the records,
pick who to add and who to remove, optionally choose the subscription
subtypes, and the change is applied to the whole selection at once - with a
summary of exactly how many follower entries were added and removed.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/followers_bulk_wizard_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
