# -*- coding: utf-8 -*-
# Part of record_owner_bulk_reassign. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Reassign Records in Bulk',
    'version': '14.0.1.0.0',
    'summary': 'Hand over every record of a leaving salesperson or team member in one step.',
    'description': """
When a salesperson or a project member leaves, every record they own has to be
reassigned by hand, one form at a time.

This module adds a "Reassign Owner" action: select the records - or simply pick
"all records of user X" - choose the new owner, and apply. The responsible field
of the model is detected automatically (user_id, user_ids or activity_user_id),
a note is logged on every record that changed, and a summary tells you how many
records were reassigned, how many were already assigned and how many were
skipped because you may not write them.

Access rights are always respected: the reassignment runs as the current user,
never with elevated privileges.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/record_owner_reassign_wizard_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
