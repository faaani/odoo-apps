# -*- coding: utf-8 -*-
# Part of bulk_tag_manager. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Add and Remove Tags in Bulk',
    'version': '18.0.1.0.0',
    'summary': 'Add or remove tags on many records at once from the Action menu, '
               'without erasing the tags already there.',
    'description': """
Tagging is how teams segment their data - but Odoo only lets you tag one record
at a time. Labelling forty contacts as "Newsletter", or clearing a "Prospect"
tag off a hundred leads, means opening every single record.

This module adds "Add / Remove Tags" to the Action menu of the list views of
every model that has tags - contacts, leads, tasks, events, campaigns, products
on 16.0 and later, and your own custom models. Select the records, pick the tag
field, type the tags to add and the tags to remove, and apply in one step.

Only tag fields are ever offered: a many2many named like a tag field, or one
pointing at a tag or category model. Other many2many fields are never listed and
are refused server-side, so this wizard cannot become a blind mass editor.

Tags that are already on a record are never touched: the module adds and removes
individual tags instead of replacing the whole tag set, so a colleague's tags
survive your bulk update. Records you are not allowed to write are skipped and
reported instead of raising an error in the middle of the batch.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/bulk_tag_wizard_views.xml',
        'data/bulk_tag_bindings.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
