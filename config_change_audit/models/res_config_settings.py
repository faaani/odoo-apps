# -*- coding: utf-8 -*-
# Part of config_change_audit. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

from .config_change_audit import (
    NO_SECRET_SENTINEL, PARAM_ENABLED, PARAM_RETENTION, PARAM_SECRET_PATTERNS,
)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # explicit get/set: a default-True Boolean and a "0 means keep for ever"
    # Integer are both erased by set_param(False/0) when bound with
    # config_parameter=, because get_param() falls back to the default for any
    # falsy stored value.
    config_audit_enabled = fields.Boolean(
        string='System Parameter Audit Trail',
        help='Record every system parameter that is created, changed or deleted.')
    config_audit_retention_days = fields.Integer(
        string='Keep History (days)',
        help='A daily scheduled action deletes audit rows older than this. '
             'Set 0 to keep the history for ever.')
    config_audit_secret_patterns = fields.Char(
        string='Mask Keys Containing',
        help='Comma-separated, case-insensitive fragments. A parameter whose key '
             'contains one of them has its values stored as ******** instead of '
             'the real content. Leave empty to mask nothing.')

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        settings = self.env['config.change.audit']._config_audit_settings()
        res.update(
            config_audit_enabled=settings['enabled'],
            config_audit_retention_days=settings['retention_days'],
            config_audit_secret_patterns=','.join(settings['secret_patterns']),
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PARAM_ENABLED, str(bool(self.config_audit_enabled)))
        icp.set_param(PARAM_RETENTION, str(max(self.config_audit_retention_days, 0)))
        icp.set_param(PARAM_SECRET_PATTERNS,
                      self.config_audit_secret_patterns or NO_SECRET_SENTINEL)
