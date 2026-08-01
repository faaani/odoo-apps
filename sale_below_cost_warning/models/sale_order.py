# -*- coding: utf-8 -*-
# Part of sale_below_cost_warning. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.

from odoo import _, api, models
from odoo.exceptions import UserError

BYPASS_GROUP = 'sale_below_cost_warning.group_sell_below_cost'
MAX_LISTED = 5


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _skip_below_cost_check(self):
        """The confirm-time block only applies to interactive internal users.

        Automated flows (online quotation acceptance, post-payment
        confirmation) run as portal/public users: raising there would leave
        a paid order stuck with nobody able to act on the error, so they are
        exempt. Integrators can also disable the check explicitly with
        context key check_sale_below_cost=False.
        """
        if not self.env.context.get('check_sale_below_cost', True):
            return True
        user = self.env.user
        if not user.has_group('base.group_user'):
            return True
        return user.has_group(BYPASS_GROUP)

    def _check_below_cost_lines(self, config):
        """Raise when any line of this order sells below cost, naming at
        most MAX_LISTED offending lines."""
        self.ensure_one()
        offending = []
        for line in self.order_line:
            below, cost = line._is_below_cost(config)
            if below:
                offending.append((line, cost))
        if not offending:
            return
        rows = ['- ' + line._below_cost_line_message(cost)
                for line, cost in offending[:MAX_LISTED]]
        if len(offending) > MAX_LISTED:
            rows.append(_('- ... and %(count)s more line(s)') % {
                'count': len(offending) - MAX_LISTED})
        raise UserError(_(
            'Cannot confirm %(order)s: some lines sell below the product '
            'cost.\n%(lines)s\nRaise the price, reduce the discount, or ask '
            'an administrator for the "Allow selling below cost" group.'
        ) % {
            'order': self.display_name,
            'lines': '\n'.join(rows),
        })

    @api.onchange('pricelist_id', 'currency_id')
    def _onchange_warn_below_cost_order(self):
        """Switching the pricelist (and with it the currency) can push
        existing lines below cost without any line being edited: re-scan
        them and warn once with an aggregate message."""
        config = self.env['sale.order.line']._below_cost_config()
        if config['mode'] == 'off':
            return
        messages = []
        for line in self.order_line:
            below, cost = line._is_below_cost(config)
            if below:
                messages.append('- ' + line._below_cost_line_message(cost))
        if not messages:
            return
        rows = messages[:MAX_LISTED]
        if len(messages) > MAX_LISTED:
            rows.append(_('- ... and %(count)s more line(s)') % {
                'count': len(messages) - MAX_LISTED})
        message = _('Some lines now sell below the product cost:')
        message += '\n' + '\n'.join(rows)
        if config['mode'] == 'block':
            message += '\n' + _(
                'Confirming this order will be blocked unless you belong '
                'to the "Allow selling below cost" group.')
        else:
            message += '\n' + _(
                'You can still save and confirm the order.')
        return {
            'warning': {
                'title': _('Selling below cost'),
                'message': message,
            }
        }

    def action_confirm(self):
        config = self.env['sale.order.line']._below_cost_config()
        if config['mode'] == 'block' and not self._skip_below_cost_check():
            for order in self:
                order._check_below_cost_lines(config)
        return super().action_confirm()
