# -*- coding: utf-8 -*-
# Part of ir_logging_viewer. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Explicit get_values/set_values instead of config_parameter=: get_param()
    # returns the field default for any falsy stored value, so switching the
    # cleanup back off could never be saved.
    ir_logging_retention_active = fields.Boolean(
        string='Delete Old Log Entries',
        help='Run a daily cleanup that deletes database log entries older than '
             'the retention window. Off by default: no entry is ever deleted '
             'until you switch this on.')
    ir_logging_retention_days = fields.Integer(
        string='Retention (days)',
        help='Number of days of log entries to keep. Entries created before '
             'that are deleted by the daily cleanup; newer entries are kept.')

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        config = self.env['ir.logging']._logging_viewer_retention()
        res.update(
            ir_logging_retention_active=config['active'],
            ir_logging_retention_days=config['days'],
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.logging']._logging_viewer_set_retention(
            self.ir_logging_retention_active,
            self.ir_logging_retention_days,
        )
