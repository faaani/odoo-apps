# -*- coding: utf-8 -*-
# Part of partner_private_address_type. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Odoo 17.0 removed the 'private' value that existed through 16.0.
    # 'set default' keeps uninstall safe: any leftover row falls back to
    # 'contact' if the uninstall hook could not run.
    type = fields.Selection(
        selection_add=[('private', 'Private Address')],
        ondelete={'private': 'set default'},
    )

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
