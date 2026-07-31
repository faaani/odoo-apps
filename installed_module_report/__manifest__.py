# -*- coding: utf-8 -*-
# Part of installed_module_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Installed Modules Report',
    'version': '19.0.1.0.0',
    'summary': 'Read-only inventory of installed modules: version, author, licence, '
               'core / OCA / third-party classification, dependencies and reverse dependencies.',
    'description': """
Before an upgrade or an audit somebody always asks the same three questions:
what is actually installed on this database, how much of it is third party, and
what breaks if we remove this one? The Apps screen answers none of them well.

This module adds a read-only report over the module list with, for every
installed module:

* technical name, module name, installed version, author and licence,
* an origin classification - Odoo S.A. (core), Odoo S.A. (Enterprise),
  Odoo Community Association (OCA), other third party, or author not declared -
  worked out from the declared author and licence,
* an approximate install date, taken from the oldest external ID the module
  created (Odoo stores no real install date),
* the number and the list of its direct dependencies,
* the number and the list of the installed modules that depend on IT.

Filters ship for the three questions an audit starts with: third-party modules
only, modules whose licence is not LGPL-3, and modules that are installed but
are not part of any app - not an application themselves, not auto-installed
glue, and no other installed module depends on them.

The report is a single SQL view with grouped sub-queries; the dependency lists
are resolved with one query per page, never one query per module. It is
read-only in the strongest sense: it has no write, create or delete access, and
it never installs, upgrades or uninstalls anything. Visible to Settings /
Administration users only.

How the classification works, and where it can be wrong, is written on the
report itself and on the store listing - it reads the manifest, and a manifest
can lie.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/installed_module_report_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
