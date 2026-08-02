# -*- coding: utf-8 -*-
# Part of auth_login_lockout. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

from .auth_login_attempt import (
    PARAM_ALERT, PARAM_ENABLED, PARAM_LOCK_MINUTES,
    PARAM_MAX_ATTEMPTS, PARAM_RETENTION_DAYS,
)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # explicit get/set instead of config_parameter=: a Boolean that defaults to
    # True can never be turned off through get_param, which returns the default
    # for every falsy stored value
    lockout_enabled = fields.Boolean(
        string='Lock Out Repeated Failed Logins',
        help='Refuse further login attempts for a login that has failed too many times.')
    lockout_max_attempts = fields.Integer(
        string='Failed Attempts Allowed',
        help='Number of failed attempts for the same login before it is locked out.')
    lockout_minutes = fields.Integer(
        string='Lockout Duration (minutes)',
        help='How long the login stays refused. The lockout always expires by itself.')
    lockout_alert = fields.Boolean(
        string='E-mail Administrators On Lockout',
        help='Send a message to every Settings administrator when a lockout starts.')
    lockout_retention_days = fields.Integer(
        string='Keep Attempts For (days)',
        help='A scheduled action deletes recorded login attempts older than this.')

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        config = self.env['auth.login.attempt']._lockout_config()
        res.update(
            lockout_enabled=config['enabled'],
            lockout_max_attempts=config['max_attempts'],
            lockout_minutes=config['lock_minutes'],
            lockout_alert=config['alert'],
            lockout_retention_days=config['retention_days'],
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PARAM_ENABLED, str(bool(self.lockout_enabled)))
        icp.set_param(PARAM_ALERT, str(bool(self.lockout_alert)))
        # a threshold of zero would lock every account out on sight, and a zero
        # duration or retention makes no sense either
        icp.set_param(PARAM_MAX_ATTEMPTS, str(max(self.lockout_max_attempts, 1)))
        icp.set_param(PARAM_LOCK_MINUTES, str(max(self.lockout_minutes, 1)))
        icp.set_param(PARAM_RETENTION_DAYS, str(max(self.lockout_retention_days, 1)))
