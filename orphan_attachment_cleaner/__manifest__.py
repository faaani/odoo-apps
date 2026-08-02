# -*- coding: utf-8 -*-
# Part of orphan_attachment_cleaner. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Find Orphaned Attachments',
    'version': '18.0.1.0.0',
    'summary': 'Report attachments whose record or model no longer exists, with the space they waste.',
    'description': """
Deleting a record does not always remove the files attached to it. After data
imports, module uninstalls and failed jobs, attachments are left pointing at a
record that is gone - or at a model that no longer exists in the database at
all. Nothing ever cleans them up, and they keep consuming filestore space
forever.

This module adds a read-only scan under Settings that lists those orphaned
attachments grouped by model, tells you why each group is orphaned (the model
disappeared, or the record did), and shows how much space each group would
give back.

The scan never changes anything. Deleting is a separate, explicitly confirmed
action reserved for Settings administrators, and it only removes exactly the
attachments the scan reported.

Free-standing user files (no model at all), web assets and module data, and
binary-field storage are never reported and never deleted.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/orphan_attachment_scan_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
