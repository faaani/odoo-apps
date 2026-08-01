# -*- coding: utf-8 -*-
# Part of sale_below_cost_warning. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.

from odoo import _, api, fields, models

PARAM_MODE = 'sale_below_cost_warning.mode'
PARAM_FLAG_ZERO = 'sale_below_cost_warning.flag_zero_price'
MODES = ('off', 'warn', 'block')
DEFAULT_MODE = 'warn'


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.model
    def _below_cost_config(self):
        """Read the module settings from ir.config_parameter.

        get_param() returns the DEFAULT for any falsy stored value, so the
        stored values are always truthy strings: the mode is one of
        'off'/'warn'/'block' (falling back to 'warn' when unset or invalid)
        and the boolean is stored as 'True'/'False'.
        """
        icp = self.env['ir.config_parameter'].sudo()
        mode = icp.get_param(PARAM_MODE)
        if mode not in MODES:
            mode = DEFAULT_MODE
        return {
            'mode': mode,
            'flag_zero_price': icp.get_param(PARAM_FLAG_ZERO) == 'True',
        }

    def _below_cost_effective_price(self):
        """Unit price after the line discount, in the order currency."""
        self.ensure_one()
        return self.price_unit * (1.0 - (self.discount or 0.0) / 100.0)

    def _is_below_cost(self, config=None):
        """Single source of truth for the onchange warning and the
        confirm-time block. Returns (below, cost) where cost is the product
        standard cost converted to the order currency and to the line's unit
        of measure.

        Rules:
        * section/note lines and lines without a product are never flagged;
        * a product whose standard cost is zero is skipped (a zero cost
          usually means "not configured") unless zero-price flagging is on,
          in which case a zero or negative effective price is flagged;
        * otherwise the line is flagged when the effective unit price
          (after discount) is below the converted cost, compared at the
          order currency's rounding.
        """
        self.ensure_one()
        if config is None:
            config = self._below_cost_config()
        if self.display_type or not self.product_id:
            return False, 0.0
        order = self.order_id
        company = (order.company_id or self.company_id)._origin
        if not company:
            company = self.env.company
        currency = order.currency_id or company.currency_id
        product = self.product_id.with_company(company)
        # standard_price is per product UoM in the company currency
        cost = product.standard_price
        line_uom = self.product_uom_id
        if line_uom and line_uom != product.uom_id:
            cost = product.uom_id._compute_price(cost, line_uom)
        company_currency = company.currency_id
        if currency and company_currency and currency != company_currency:
            date = (order.date_order and order.date_order.date()
                    or fields.Date.context_today(self))
            cost = company_currency._convert(cost, currency, company, date)
        price = self._below_cost_effective_price()
        if currency.is_zero(cost):
            if config['flag_zero_price'] \
                    and currency.compare_amounts(price, 0.0) <= 0:
                return True, 0.0
            return False, 0.0
        return currency.compare_amounts(price, cost) < 0, cost

    @api.model
    def _below_cost_format_amount(self, value, currency):
        """Format an amount with the currency's own decimal places, so a
        3-decimal currency (e.g. KWD) never shows two equal-looking
        amounts that differ on the third decimal."""
        return '%.*f' % (currency.decimal_places, currency.round(value))

    def _below_cost_line_message(self, cost):
        """One human-readable reason line, used by the warning and the
        blocking error."""
        self.ensure_one()
        currency = self.order_id.currency_id or self.env.company.currency_id
        name = self.product_id.display_name or self.name or _('this line')
        if currency.is_zero(cost):
            return _('"%(line)s" has a zero or negative unit price.') % {
                'line': name}
        return _(
            '"%(line)s" sells at %(price)s %(currency)s per '
            '%(uom)s after discount, below its cost of %(cost)s '
            '%(currency)s.'
        ) % {
            'line': name,
            'price': self._below_cost_format_amount(
                self._below_cost_effective_price(), currency),
            'cost': self._below_cost_format_amount(cost, currency),
            'currency': currency.name,
            'uom': self.product_uom_id.display_name or _('unit'),
        }

    @api.onchange('product_id', 'price_unit', 'discount', 'product_uom_id')
    def _onchange_warn_below_cost(self):
        config = self._below_cost_config()
        if config['mode'] == 'off':
            return
        below, cost = self._is_below_cost(config)
        if not below:
            return
        message = self._below_cost_line_message(cost)
        if config['mode'] == 'block':
            message += _(
                ' Confirming this order will be blocked unless you belong '
                'to the "Allow selling below cost" group.')
        else:
            message += _(' You can still save and confirm the order.')
        return {
            'warning': {
                'title': _('Selling below cost'),
                'message': message,
            }
        }
