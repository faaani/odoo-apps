# -*- coding: utf-8 -*-
# Part of mail_autofollow_optout. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Stop Auto-Following Records',
    'version': '18.0.1.0.1',
    'summary': 'Let each user opt out of being subscribed automatically to every record they touch - without losing manual Follow.',
    'description': """
Odoo subscribes you as a follower of every record you comment on or get
assigned, and your Inbox fills with notifications you never asked for. The
only escape is unfollowing records one by one, forever.

This module adds a single preference: "Do not follow records automatically".
Users who tick it stop being auto-subscribed, while the Follow button keeps
working normally whenever they do want updates.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Productivity/Discuss',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail'],
    'data': ['views/res_users_views.xml'],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
