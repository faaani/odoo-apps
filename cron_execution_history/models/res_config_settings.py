# -*- coding: utf-8 -*-
# Part of cron_execution_history. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

from .cron_execution_history import (
    PARAM_ENABLED, PARAM_LOG_SUCCESS, PARAM_RETENTION_DAYS,
)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Explicit get_values/set_values instead of config_parameter=: get_param()
    # hands back the DEFAULT for any falsy stored value, so a default-True
    # Boolean could never be switched off and a retention of 0 could never be
    # saved.
    cron_history_enabled = fields.Boolean(
        string='Scheduled Action History',
        help='Record every run of every scheduled action.',
    )
    cron_history_log_success = fields.Boolean(
        string='Record Successful Runs',
        help='Untick to keep failures only, which makes the history much smaller.',
    )
    cron_history_retention_days = fields.Integer(
        string='Keep History For (days)',
        help='A daily cleanup deletes history rows older than this. '
             'Set 0 to keep the history forever.',
    )

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        config = self.env['cron.execution.history']._history_config()
        res.update(
            cron_history_enabled=config['enabled'],
            cron_history_log_success=config['log_success'],
            cron_history_retention_days=config['retention_days'],
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PARAM_ENABLED, str(bool(self.cron_history_enabled)))
        icp.set_param(PARAM_LOG_SUCCESS, str(bool(self.cron_history_log_success)))
        icp.set_param(PARAM_RETENTION_DAYS,
                      str(max(self.cron_history_retention_days or 0, 0)))
