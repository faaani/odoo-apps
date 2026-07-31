# -*- coding: utf-8 -*-
# Part of partner_private_address_type. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, models
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.constrains('partner_id', 'active')
    def _check_partner_not_private_address(self):
        """Mirror of the res.partner constraint: an active user must never be
        attached to a private-address partner they could not see."""
        for user in self:
            if user.active and user.sudo().partner_id.type == 'private':
                raise ValidationError(_(
                    'User "%s" cannot be linked to a contact whose address '
                    'type is Private Address. Change the contact\'s address '
                    'type first.'
                ) % user.login)
