# -*- coding: utf-8 -*-
# Part of sale_below_cost_warning. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Warn or Block Selling Below Cost',
    'version': '16.0.1.0.0',
    'summary': 'Warn while quoting and optionally block confirmation when a sale order line sells below the product cost, with currency and unit-of-measure conversion.',
    'description': """
A discounted line, a mistyped price or a stale pricelist can quietly sell a
product below what it costs you. Odoo accepts any unit price without a
second look.

This module compares each sale order line's unit price (after discount)
against the product's standard cost - converted to the order currency at the
order date and to the line's unit of measure - and, depending on a mode
setting (Off / Warn / Block, default Warn):

* while editing, a non-blocking warning pops up naming the line, its price
  and its cost;
* in Block mode, confirming the order raises an error listing the offending
  lines (capped at 5) - unless the user belongs to the "Allow selling below
  cost" group.

Products with a zero standard cost are skipped (a zero cost usually means
"not configured") unless the optional zero-price flagging is enabled.
Section and note lines are ignored. Compares against the standard cost
field, not landed or actual cost. No new models.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Sales/Sales',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['sale'],
    'data': [
        'security/res_groups.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
