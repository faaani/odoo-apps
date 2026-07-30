# -*- coding: utf-8 -*-
# Part of sale_line_description_delivery. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import models


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_custom_move_fields(self):
        # copies values['description_picking'] (set by the sale line) onto the
        # stock move, overriding the product-based default
        fields = super(StockRule, self)._get_custom_move_fields()
        fields.append('description_picking')
        return fields
