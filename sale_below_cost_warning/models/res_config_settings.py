# -*- coding: utf-8 -*-
# Part of sale_below_cost_warning. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.

from odoo import fields, models

from .sale_order_line import DEFAULT_MODE, PARAM_FLAG_ZERO, PARAM_MODE


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Explicit get_values/set_values instead of config_parameter=: get_param()
    # returns the DEFAULT for any falsy stored value, which would make a
    # non-default selection impossible to reset and a default-False boolean
    # impossible to switch back off reliably.
    below_cost_mode = fields.Selection(
        [
            ('off', 'Off'),
            ('warn', 'Warn while quoting'),
            ('block', 'Warn and block confirmation'),
        ],
        string='Below-Cost Sales Check',
        help='Warn while editing a quotation when a line sells below the '
             'product cost, and optionally block order confirmation.')
    below_cost_flag_zero_price = fields.Boolean(
        string='Also Flag Zero-Price Lines',
        help='Also flag lines with a zero (or negative) unit price on '
             'products that have no cost configured.')

    def get_values(self):
        res = super().get_values()
        config = self.env['sale.order.line']._below_cost_config()
        res.update(
            below_cost_mode=config['mode'],
            below_cost_flag_zero_price=config['flag_zero_price'],
        )
        return res

    def set_values(self):
        super().set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PARAM_MODE, self.below_cost_mode or DEFAULT_MODE)
        icp.set_param(PARAM_FLAG_ZERO,
                      str(bool(self.below_cost_flag_zero_price)))
