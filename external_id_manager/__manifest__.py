# -*- coding: utf-8 -*-
# Part of external_id_manager. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'External ID Manager',
    'version': '14.0.1.0.0',
    'summary': 'Search external IDs (XML IDs) by module, model, name or target record, and spot broken references.',
    'description': """
External IDs (ir.model.data) drive imports, data files and env.ref(), but the
standard way to look one up is to switch on developer mode and browse a raw
list that shows a model name and a numeric id - never the record behind it.

This module adds an administrator screen that:

* searches external IDs by module, by model, by identifier, or by the *display
  name of the record they point to*,
* resolves that record and shows its name, with a button to open it,
* flags BROKEN references - external IDs whose record no longer exists - and
  entries whose model is not installed any more,
* copies the full "module.name" identifier to the clipboard in one click,
* splits entries created by module data files from entries left behind by
  spreadsheet imports and exports (__import__ / __export__),
* groups by module, model, source or creation date, and exports to spreadsheet.

Read-only by design. The single write operation offered is deleting an entry
that is already broken, behind a confirmation dialog and reserved to Settings
administrators. Live external IDs can never be deleted from this screen:
removing one silently breaks module upgrades, because the upgrade would create
a duplicate record instead of updating the existing one.

Record names are resolved in bulk, grouped per model - one existence query and
one name query per model, never one query per line.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/external_id_entry_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
