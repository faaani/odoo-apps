# -*- coding: utf-8 -*-
# Part of field_help_editor. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Edit Field Labels and Tooltips',
    'version': '18.0.1.0.0',
    'summary': 'Rename any field label and write your own tooltip from a simple admin screen, with one-click reset to the original.',
    'description': """
Every implementer eventually wants to call a field something else, or to explain
what a field means in this particular company. Today that means switching on
developer mode and hunting through thousands of rows in Technical / Fields.

This module gives Settings administrators a friendly screen instead:

* pick a model, see its user-facing fields with their current label and tooltip,
* edit the label and the tooltip straight in the list,
* reset a field to its original label and tooltip with one click,
* review every customization ever made on a dedicated screen, and revert them
  all from there.

The first time a field is customized, its original label and tooltip are stored,
so "Reset" restores exactly what Odoo shipped - not an approximation.

Bookkeeping columns (create_uid, write_uid, create_date, write_date,
display_name, id and anything starting with an underscore) are hidden by
default; a single filter shows them again.

Labels and tooltips are translatable: you always edit the language of your own
user session, the screen tells you which one that is, and the other languages
keep their own values.

Restricted to Settings administrators. Nothing else in the database is touched:
no field is created, renamed, moved or deleted - only the label and the help
text a field shows to users.

Technical note: so that a tooltip can also be added to fields that ship without
one, the module refines how Odoo resolves a field's help text. On a server
hosting several databases in a single process, that refinement applies only to
the databases where this module is installed.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/field_help_customization_views.xml',
        'views/ir_model_fields_views.xml',
        'views/field_help_editor_menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
