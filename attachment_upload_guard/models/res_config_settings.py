# -*- coding: utf-8 -*-
# Part of attachment_upload_guard. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

from .ir_attachment import (
    DEFAULT_BLOCKED, NO_BLOCKED_SENTINEL,
    PARAM_BLOCKED_EXT, PARAM_ENABLED, PARAM_MAX_MB,
)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # explicit get/set: a default-True Boolean and a 0-means-unlimited Integer
    # are both erased by set_param(False/0) when bound with config_parameter=
    attachment_guard_enabled = fields.Boolean(
        string='Attachment Upload Policy',
        help='Enforce a blocked file type list and a maximum attachment size.')
    attachment_guard_extensions = fields.Char(
        string='Blocked File Types',
        help='Comma-separated extensions, e.g. exe,bat,msi. Leave empty to allow every type.')
    attachment_guard_max_mb = fields.Integer(
        string='Maximum Size (MB)',
        help='Largest attachment a user may upload. Set 0 for no size limit.')

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        config = self.env['ir.attachment']._upload_guard_config()
        res.update(
            attachment_guard_enabled=config['enabled'],
            attachment_guard_extensions=','.join(sorted(config['blocked'])),
            attachment_guard_max_mb=config['max_mb'],
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PARAM_ENABLED, str(bool(self.attachment_guard_enabled)))
        icp.set_param(PARAM_BLOCKED_EXT,
                      self.attachment_guard_extensions or NO_BLOCKED_SENTINEL)
        icp.set_param(PARAM_MAX_MB, str(max(self.attachment_guard_max_mb, 0)))
