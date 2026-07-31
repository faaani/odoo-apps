# -*- coding: utf-8 -*-
# Part of default_value_manager. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Manage Default Values',
    'version': '17.0.1.0.0',
    'summary': 'List, search and clean up the user and company default values stored in ir.default.',
    'description': """
"Set Default" writes a row in ir.default and there is no screen to look at it
again. Months later a field keeps pre-filling with a stale value and nobody
knows which default does it, who it applies to, or how to remove it.

This module adds an administrator screen listing every default value with:

* the model and the field, by label and by technical name,
* the stored value RENDERED READABLE - many2one ids resolved to the record
  name, booleans as Yes/No, selections as their label, dates as they are set,
* the scope: all users or one named user, all companies or one named company,
* the optional condition the default is restricted to,
* a status column that flags entries whose model or field no longer exists
  (ORPHANED), entries pointing at a record that has been deleted, and entries
  whose stored JSON is not readable - none of which make the list crash.

Filters for orphaned entries, personal versus global defaults, company-specific
versus all-company defaults, and a search on the readable value itself.
Group by model, field, user or company, and export to spreadsheet.

Clean-up is deliberate: deleting is a confirmed action on the rows you select,
never a side effect of opening the screen, and nothing else in the database is
touched - removing a default only stops that field from pre-filling.

Adding a default from the screen is optional and validated: the field must
exist on the model and the value must be convertible to that field's type
(a record name or id for many2one, the key or the label for a selection),
and the entry is written through the supported ir.default.set() API.

Restricted to the Administration / Settings group.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'security/default_value_manager_rules.xml',
        'views/default_value_entry_views.xml',
        'wizard/default_value_wizard_views.xml',
        'views/default_value_menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
