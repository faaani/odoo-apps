# -*- coding: utf-8 -*-
# Part of auto_deactivate_dormant_users. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

from .res_users import (
    DEFAULT_DAYS,
    PARAM_DAYS,
    PARAM_ENABLED,
    PARAM_INCLUDE_NEVER_LOGGED,
    PARAM_NOTIFY_ADMINS,
)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dormancy_enabled = fields.Boolean(
        string='Auto Deactivate Dormant Users',
        config_parameter=PARAM_ENABLED,
        help='Archive internal users automatically after the dormancy period below.',
    )
    dormancy_days = fields.Integer(
        string='Dormancy Period (days)',
        config_parameter=PARAM_DAYS,
        default=DEFAULT_DAYS,
        help='Users who have not logged in for this many days are archived. Minimum 7.',
    )
    dormancy_include_never_logged = fields.Boolean(
        string='Include Users Who Never Logged In',
        config_parameter=PARAM_INCLUDE_NEVER_LOGGED,
        help='Also archive users who never logged in, counting from their creation date.',
    )
    # No config_parameter here on purpose: set_param(False) deletes the key and a
    # default=True field then silently re-enables itself on reload. Stored as an
    # explicit 'True'/'False' string via get_values/set_values instead.
    dormancy_notify_admins = fields.Boolean(
        string='Notify Administrators',
        help='Send Settings administrators an email summary whenever users are archived.',
    )

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        icp = self.env['ir.config_parameter'].sudo()
        res['dormancy_notify_admins'] = icp.get_param(PARAM_NOTIFY_ADMINS, 'True') == 'True'
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PARAM_NOTIFY_ADMINS, str(bool(self.dormancy_notify_admins)))
