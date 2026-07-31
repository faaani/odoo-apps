# -*- coding: utf-8 -*-
# Part of partner_private_address_type. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Through 16.0 core already ships the 'private' selection value on
    # res.partner.type: this variant only hardens it (record rules in
    # security/security.xml plus the constraints below).

    @api.constrains('type')
    def _check_private_type_not_linked_to_user(self):
        """A user hidden from themselves cannot log in or use their profile:
        never allow the Private Address type on a partner that is linked to
        an active user."""
        for partner in self:
            if partner.type == 'private' and partner.sudo().user_ids:
                raise ValidationError(_(
                    'Contact "%s" is linked to an active user and cannot use '
                    'the Private Address type. Hiding a user\'s own contact '
                    'record would break their login and profile.'
                ) % partner.sudo().display_name)
