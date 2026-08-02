# -*- coding: utf-8 -*-
# Part of attachment_storage_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Attachment Storage Report',
    'version': '18.0.1.0.0',
    'summary': 'See which models, users and files are eating your database and filestore space.',
    'description': """
When an Odoo database or filestore starts filling the disk, there is no screen
that answers the only question that matters: what is actually taking the space?

This module adds a read-only storage report for administrators. It groups every
attachment by model and by uploading user, splits the total between the
filestore and the database, and lists the largest files, with a minimum-size
filter so the thousands of tiny records stop hiding the real offenders.

All figures are aggregated by PostgreSQL, so the report stays fast on databases
with hundreds of thousands of attachments. It therefore reports on every
attachment in the selected companies, including documents the administrator
would not be able to open individually, which is why access is restricted to
the Settings group.

Nothing is ever deleted automatically: an optional cleanup lets you tick
individual files and remove them only after an explicit confirmation, and it
refuses files that are the value of a binary field so a logo or a photo can
never be erased by mistake.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/attachment_storage_report_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
