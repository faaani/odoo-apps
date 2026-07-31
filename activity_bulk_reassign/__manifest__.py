# -*- coding: utf-8 -*-
# Part of activity_bulk_reassign. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Reassign Activities in Bulk',
    'version': '19.0.1.0.0',
    'summary': 'Move all open activities of one user to another in a single step.',
    'description': """
When someone leaves the company or goes on holiday, their open activities - 
to-dos, calls, meetings - stay assigned to them. Odoo only lets you move them
one record at a time.

This wizard picks up every open activity of a user, optionally narrowed by
activity type and due-date range, shows how many were found, and reassigns
them all to a colleague in one click. A note is logged on each affected
document so the handover stays auditable.

Only the activities the current user is allowed to modify are ever touched,
and finished or cancelled activities are always left alone.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/activity_bulk_reassign_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
