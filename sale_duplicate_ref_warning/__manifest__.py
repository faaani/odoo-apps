# -*- coding: utf-8 -*-
# Part of sale_duplicate_ref_warning. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Duplicate Customer Reference Check on Sale Orders',
    'version': '16.0.1.0.0',
    'summary': 'Warn while quoting and block confirmation when a customer PO reference is already used on another order of the same customer.',
    'description': """
The same customer purchase order keyed in twice means duplicate orders,
duplicate deliveries and duplicate invoices. Odoo accepts any value in the
Customer Reference field without a second look.

This module checks the reference against every other non-cancelled sale
order of the same commercial partner (trimmed, case-insensitive):

* while editing, a non-blocking warning pops up naming the colliding orders;
* on confirmation, a blocking error stops the duplicate - unless the user
  belongs to the "Allow duplicate customer references" group.

Checks sale orders only (not invoices). No new models, no configuration.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Sales/Sales',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['sale'],
    'data': [
        'security/res_groups.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
