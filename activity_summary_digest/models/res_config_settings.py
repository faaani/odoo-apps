# -*- coding: utf-8 -*-
# Part of activity_summary_digest. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, fields, models
from odoo.exceptions import AccessError

from .res_users import OPTIN_FIELD, PARAM_ENABLED


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # explicit get/set: a default-True boolean bound with config_parameter=
    # can never be switched off, because get_param() returns the default for
    # every falsy stored value
    activity_digest_enabled = fields.Boolean(
        string='Daily Activity Digest',
        help='Master switch for the daily digest email. Turn it off and no '
             'digest is sent to anybody, whatever each user asked for.',
    )

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res['activity_digest_enabled'] = self.env['res.users']._activity_digest_enabled()
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            PARAM_ENABLED, str(bool(self.activity_digest_enabled)))

    def action_activity_digest_enable_all(self):
        """Opt every active internal user into the digest in one click."""
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only administrators can change this setting.'))
        users = self.env['res.users'].search([
            ('active', '=', True),
            ('share', '=', False),
        ])
        users.write({OPTIN_FIELD: True})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Daily Activity Digest'),
                'message': _('The digest is now switched on for %s internal '
                             'user(s). Each of them can switch it off again in '
                             'their own preferences.') % len(users),
                'sticky': False,
            },
        }
