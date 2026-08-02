# -*- coding: utf-8 -*-
# Part of sale_line_description_delivery. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Sale Line Description on Delivery',
    'version': '19.0.1.0.1',
    'summary': 'Show the description typed on the sale order line on the transfer and the delivery slip - not just the product name.',
    'description': """
The description you type on a sale order line never reaches the warehouse:
transfers and delivery slips only show the product's own description. This
module carries the sale order line description onto the stock moves, so
pickers and customers see exactly what was sold - engraving texts, packing
notes, customer references.

No configuration. Install and every new confirmed order does the right thing.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Inventory/Inventory',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['sale_stock'],
    'data': [],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
