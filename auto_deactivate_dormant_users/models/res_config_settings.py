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
    # No config_parameter here either: set_param() deletes the key for any
    # falsy value, so a period cleared to 0 would silently come back as the
    # 90-day default on the next reload. Stored as an explicit string ('0'
    # included) via get_values/set_values, like the Boolean below.
    dormancy_days = fields.Integer(
        string='Dormancy Period (days)',
        default=DEFAULT_DAYS,
        help='Users who have not logged in for this many days are archived. '
             'The scheduled action never uses less than 7 days, whatever is '
             'stored here.',
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
        # None as the sentinel for "never saved": get_param's default of False
        # would be int()-ed to 0 and a fresh database would show 0 instead of
        # the real default. A stored '0' on the other hand IS returned as 0.
        raw_days = icp.get_param(PARAM_DAYS, None)
        if raw_days is None:
            res['dormancy_days'] = DEFAULT_DAYS
        else:
            try:
                res['dormancy_days'] = int(raw_days)
            except ValueError:
                res['dormancy_days'] = DEFAULT_DAYS
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PARAM_NOTIFY_ADMINS, str(bool(self.dormancy_notify_admins)))
        # str(int(...)): '0' is a truthy STRING, so set_param stores it instead
        # of deleting the key — the value the user saved is the value read back.
        icp.set_param(PARAM_DAYS, str(int(self.dormancy_days or 0)))
