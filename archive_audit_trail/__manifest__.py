# -*- coding: utf-8 -*-
# Part of archive_audit_trail. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Archive Audit Trail',
    'version': '18.0.1.0.1',
    'summary': 'Log who archived or unarchived a record, and when, right in its chatter.',
    'description': """
"Where did that customer go?" Archiving is a one-click action that hides
records from everyone, and Odoo keeps no trace of who did it.

This module posts a short note in the record's chatter every time it is
archived or restored, naming the user and the moment. It applies to every
model with a chatter and an active flag — customers, products, employees,
pricelists — with no configuration.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail'],
    'data': [],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
