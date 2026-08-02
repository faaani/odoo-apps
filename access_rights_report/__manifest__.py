# -*- coding: utf-8 -*-
# Part of access_rights_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Access Rights Matrix',
    'version': '17.0.1.0.0',
    'summary': 'Read-only audit matrix of every access control line and record rule: model x group x read/write/create/delete.',
    'description': """
Answering "which groups can delete invoices?" in standard Odoo means opening
Settings / Technical / Access Rights and paging through the list one line at a
time. This module turns those lines into a matrix you can filter, group and
export.

What you get
------------
* **Access Rights Matrix** - one row per model and group, with a read, write,
  create and delete tick. Several access control lines for the same model and
  group are merged the way Odoo merges them: a permission is granted when at
  least one active line grants it.
* Filters by model, by group and by permission - "grants Delete", "grants
  Create", "full access", "read only", "grants nothing".
* Group by model or by group, so an auditor can export either shape.
* **Rights by Group** - pick a group and see every model it can reach,
  including the rights it inherits from the groups it implies and the rights
  every user gets from access control lines that have no group at all. Each row
  says whether the right is direct, inherited or global, and which group
  supplies it.
* **Record Rules** - the ir.rule records with their domain, the operations they
  apply to, whether they are global or attached to groups, and which groups.

Honest limitations
------------------
* The matrix itself is *literal*: it reports the access control lines exactly as
  recorded, it does **not** expand implied (inherited) groups. The "Rights by
  Group" view is the one that expands them, transitively, through
  res.groups.implied_ids.
* Only active access control lines and, by default, active record rules are
  taken into account - an unticked line is ignored by Odoo, so it is ignored
  here too. Inactive record rules can be shown with a filter.
* Models with no access control line at all are listed with a "No access rule"
  flag: nobody but the superuser can touch them. Abstract models (mixins) are
  hidden by default because they store nothing and never need a line.
* Field-level access (ir.model.fields groups) and menu visibility are **not**
  covered.
* "Rights by Group" expands to one row per group per reachable model. On a large
  database with many apps installed that is in the order of a hundred thousand
  rows, and a database view carries no index, so the first load and a full export
  take a few seconds. The matrix itself stays small (a few thousand rows).

Read-only by design
-------------------
The three reports are SQL views over ir.model.access, res.groups and ir.rule.
The module never writes to ir.model.access or ir.rule, never creates, edits or
deletes a rule, and never uses sudo. Every screen is restricted to Settings /
Administration users.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/access_rights_matrix_views.xml',
        'views/access_rights_group_views.xml',
        'views/access_rights_rule_views.xml',
        'views/access_rights_menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
