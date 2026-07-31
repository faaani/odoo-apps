# -*- coding: utf-8 -*-
# Part of sale_duplicate_ref_warning. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.

from odoo import _, api, models
from odoo.exceptions import ValidationError

BYPASS_GROUP = 'sale_duplicate_ref_warning.group_allow_duplicate_ref'
MAX_LISTED = 5
SEARCH_CAP = 200


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _find_duplicate_client_ref(self):
        """Other non-cancelled sale orders of the same commercial partner and
        company whose customer reference equals ours, trimmed and
        case-insensitive.

        The search is elevated (sudo) so duplicates owned by other salespeople
        - hidden from this user by the "Personal Orders" record rule - are
        still detected; it is a uniqueness probe, not an access decision, and
        _format_duplicate_ref_orders() only ever names orders the current user
        is allowed to read. Returns at most MAX_LISTED + 1 orders so callers
        can tell whether the list shown to the user was truncated.
        """
        self.ensure_one()
        ref = (self.client_order_ref or '').strip()
        # In an onchange, ids are NewId placeholders: resolve through _origin.
        commercial = self.partner_id.commercial_partner_id._origin
        if not ref or not commercial.id:
            return self.browse()
        # ilike wraps the value in %...%: escape the wildcards first, then
        # settle trimmed case-insensitive EQUALITY in Python, so stored
        # references with surrounding whitespace are caught as well.
        pattern = ref.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        company_id = self.company_id._origin.id or self.env.company.id
        domain = [
            ('partner_id.commercial_partner_id', '=', commercial.id),
            ('client_order_ref', 'ilike', pattern),
            ('state', '!=', 'cancel'),
            ('company_id', '=', company_id),
        ]
        origin_id = self._origin.id
        if origin_id:
            domain.append(('id', '!=', origin_id))
        candidates = self.sudo().search(domain, limit=SEARCH_CAP, order='id')
        folded = ref.lower()
        duplicates = candidates.filtered(
            lambda o: (o.client_order_ref or '').strip().lower() == folded)
        return duplicates[:MAX_LISTED + 1]

    def _format_duplicate_ref_orders(self, duplicates):
        """Name the colliding orders, capped at MAX_LISTED, without leaking
        names of orders the current user cannot read."""
        visible = self.env['sale.order'].search([('id', 'in', duplicates.ids)])
        if not visible:
            # duplicates is capped at MAX_LISTED + 1: the last record is a
            # truncation sentinel, not a real count.
            if len(duplicates) > MAX_LISTED:
                return _('at least %(count)s order(s) you are not allowed to '
                         'access') % {'count': MAX_LISTED}
            return _('%(count)s order(s) you are not allowed to access') % {
                'count': len(duplicates)}
        names = ', '.join(visible[:MAX_LISTED].mapped('name'))
        if len(visible) < len(duplicates) or len(duplicates) > MAX_LISTED:
            names = _('%(orders)s and more') % {'orders': names}
        return names

    @api.onchange('client_order_ref', 'partner_id', 'company_id')
    def _onchange_duplicate_client_ref(self):
        duplicates = self._find_duplicate_client_ref()
        if duplicates:
            values = {
                'ref': (self.client_order_ref or '').strip(),
                'orders': self._format_duplicate_ref_orders(duplicates),
            }
            if self.state in ('draft', 'sent'):
                message = _(
                    'Customer reference "%(ref)s" is already used on %(orders)s '
                    'for this customer. You can still save the quotation, but '
                    'confirming it will be blocked.'
                ) % values
            else:
                # Past confirmation the reference is still editable; only the
                # confirmation-will-be-blocked wording would be wrong here.
                message = _(
                    'Customer reference "%(ref)s" is already used on %(orders)s '
                    'for this customer.'
                ) % values
            return {
                'warning': {
                    'title': _('Duplicate customer reference'),
                    'message': message,
                }
            }

    def _skip_duplicate_client_ref_check(self):
        """The confirm-time block only applies to interactive internal users.

        Automated flows (online quotation acceptance, post-payment
        confirmation) run as portal/public users: raising there would leave a
        paid order stuck with nobody able to act on the error, so they are
        exempt. Integrators can also disable the check explicitly with
        context key check_duplicate_client_ref=False.
        """
        if not self.env.context.get('check_duplicate_client_ref', True):
            return True
        user = self.env.user
        if not user.has_group('base.group_user'):
            return True
        return user.has_group(BYPASS_GROUP)

    def action_confirm(self):
        if not self._skip_duplicate_client_ref_check():
            for order in self.filtered('client_order_ref'):
                duplicates = order._find_duplicate_client_ref()
                if duplicates:
                    raise ValidationError(_(
                        'Customer reference "%(ref)s" on %(order)s is already used '
                        'on %(orders)s for the same customer.\n'
                        'Use a different reference, cancel the other order, or ask '
                        'an administrator for the "Allow duplicate customer '
                        'references" group.'
                    ) % {
                        'ref': (order.client_order_ref or '').strip(),
                        'order': order.display_name,
                        'orders': order._format_duplicate_ref_orders(duplicates),
                    })
        return super().action_confirm()
