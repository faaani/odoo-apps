# -*- coding: utf-8 -*-
# Part of password_expiry_policy. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

from .res_users import (
    DEFAULT_DAYS, MAX_DAYS, MIN_DAYS, PARAM_DAYS, PARAM_ENABLED,
)


def _clamp_days(value):
    """Keep the period inside [MIN_DAYS, MAX_DAYS] whatever was stored."""
    try:
        days = int(value)
    except (TypeError, ValueError):
        days = DEFAULT_DAYS
    return min(max(days, MIN_DAYS), MAX_DAYS)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Explicit get_values/set_values instead of config_parameter=: get_param()
    # hands back the default for any falsy stored value, so "off" and a small
    # integer could never be saved through the shorthand.
    password_expiry_enabled = fields.Boolean(
        string='Password Expiry Policy',
        help='Ask internal users for a new password once their current one '
             'reaches the age below.',
    )
    password_expiry_days = fields.Integer(
        string='Maximum Password Age (days)',
        help='Number of days a password stays valid. Values below %s days are '
             'raised to %s, so a typo cannot expire every account at once.'
             % (MIN_DAYS, MIN_DAYS),
    )

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        icp = self.env['ir.config_parameter'].sudo()
        res.update(
            password_expiry_enabled=icp.get_param(PARAM_ENABLED, 'False') == 'True',
            password_expiry_days=_clamp_days(icp.get_param(PARAM_DAYS, DEFAULT_DAYS)),
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PARAM_ENABLED, str(bool(self.password_expiry_enabled)))
        icp.set_param(PARAM_DAYS, str(_clamp_days(self.password_expiry_days)))
