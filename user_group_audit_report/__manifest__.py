# -*- coding: utf-8 -*-
# Part of user_group_audit_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'User Access Audit Report',
    'version': '16.0.1.0.0',
    'summary': 'Read-only report of every user with their groups, a privileged-access flag, archived and never-logged-in status.',
    'description': """
Answering "who can do what in this database?" today means opening the Users list
and clicking through every user, one at a time.

This module adds a read-only report with one line per user account:

* the groups on the account, as tags you can filter and group by,
* a clear flag for privileged access - Administration / Settings
  (base.group_system) and Administration / Access Rights
  (base.group_erp_manager),
* the user type (internal, portal, public, or none at all),
* whether the account is archived,
* whether it has never been used to log in, and the last login date.

Ready-made filters: has system access, internal, portal / public, archived,
never logged in, accounts with no group at all. Group by group, access level,
user type or company, then export the whole picture to a spreadsheet in one go.

Privileged flags and group counts are built from the effective groups - the
groups assigned to the account plus every group those imply, transitively - so
they stay correct on Odoo 19.0, where implied groups are no longer written onto
the user record. Everything is one grouped SQL query, no loop over users, and
nothing in your database is modified. Visible to Settings administrators only.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'security/user_group_audit_report_rules.xml',
        'views/user_group_audit_report_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
