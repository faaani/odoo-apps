# -*- coding: utf-8 -*-
# Part of data_export_audit_log. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

from .export_log import DEFAULT_RETENTION_DAYS, PARAM_RETENTION_DAYS


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # explicit get_values/set_values: an Integer bound with config_parameter=
    # can never store a falsy value (get_param returns the default for 0),
    # and 0 is meaningful here (keep logs forever)
    export_log_retention_days = fields.Integer(
        string='Export Log Retention (days)',
        help='Export audit log entries older than this many days are deleted '
             'by a daily scheduled action. Set 0 to keep logs forever.')

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update(
            export_log_retention_days=self.env['export.audit.log']
            ._get_retention_days(),
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        days = self.export_log_retention_days
        if days < 0:
            # keep both write paths consistent with _get_retention_days:
            # negatives fall back to the default instead of silently
            # becoming 0 = "keep forever"
            days = DEFAULT_RETENTION_DAYS
        self.env['ir.config_parameter'].sudo().set_param(
            PARAM_RETENTION_DAYS, str(days))
