# -*- coding: utf-8 -*-
# Part of field_rules_by_group. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Field Rules by Group',
    'version': '15.0.1.0.0',
    'summary': 'Make any field read-only, invisible or required per user group - no Studio, no code.',
    'description': """
Every Odoo project hits the same request: "this field must be read-only for
regular users", "tidy this form for that team", "make the reference
mandatory for the accounting team". Out of the box that means editing XML
views or buying Studio.

This module adds a simple rule table instead: pick a model, pick a field,
pick the user groups, tick read-only / invisible / required. The rule is
applied to every form view of that model for the matching users, and
read-only rules are also enforced server-side on create and write, so a
restricted user's direct API writes are refused as well.

Invisible and required act on form views only: invisible declutters the
form, it is not an access control and does not hide the value from API
reads or exports. Rules never apply to system administrators unless a rule
explicitly opts in, so an administrator can always repair data. Works with
any model, including custom ones.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/field_group_rule_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
