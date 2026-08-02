# -*- coding: utf-8 -*-
# Part of global_default_saved_filter. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Global Default Saved Filter',
    'version': '15.0.1.0.1',
    'summary': 'Make one shared saved filter the default view for every user - without duplicating it per user.',
    'description': """
Odoo's favorites menu makes "Use by default" and "Share with all users"
mutually exclusive, so the usual advice is to duplicate the same filter for
every single user.

This module adds a "Default for All Users" flag on shared filters. Users who
have not chosen their own default get that filter applied automatically, and
a personal default always wins over the global one - no per-user duplication,
no conflicting defaults.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'views/ir_filters_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
