# -*- coding: utf-8 -*-
# Part of sale_line_description_delivery. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import models
from odoo.tools import str2bool

PARAM_ENABLED = 'sale_line_description_delivery.enabled'


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _sld_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(PARAM_ENABLED, 'True')
        try:
            return str2bool(value)
        except ValueError:
            return True

    def _sld_picking_description(self):
        """The extra text of the sale line, without a duplicated product name.

        Sale line descriptions usually start with the product display name and
        continue with the customer-facing text on the next lines. The delivery
        report already prints the product, so only the extra text is returned;
        if the line is nothing but the product name, '' is returned and the
        default description is kept.

        The line name is rendered in the order partner's language, so the
        product name must be compared in that language too (with the current
        user's language as a fallback) or the prefix check fails on any
        multi-language database.
        """
        self.ensure_one()
        name = (self.name or '').strip()
        partner_lang = self.order_id.partner_id.lang or self.env.lang
        product_names = []
        for lang in (partner_lang, self.env.lang):
            if lang:
                pname = (self.product_id.with_context(lang=lang).display_name or '').strip()
                if pname and pname not in product_names:
                    product_names.append(pname)
        for product_name in product_names:
            if name.startswith(product_name):
                return name[len(product_name):].strip('\n ').strip()
        return name if name not in product_names else ''

    # 19.0 dropped the group_id parameter from this hook
    def _prepare_procurement_values(self):
        values = super(SaleOrderLine, self)._prepare_procurement_values()
        if self._sld_enabled():
            description = self._sld_picking_description()
            if description:
                # picked up by stock.rule via _get_custom_move_fields
                values['description_picking'] = description
        return values
