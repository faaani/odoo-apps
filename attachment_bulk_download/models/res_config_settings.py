# -*- coding: utf-8 -*-
# Part of attachment_bulk_download. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

from ..wizard.attachment_bulk_download_wizard import PARAM_MAX_MB


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # explicit get/set: bound with config_parameter=, a stored 0 reads back as
    # the default, so "no limit" could never be saved
    attachment_bulk_download_max_mb = fields.Integer(
        string='Bulk Download Limit (MB)',
        help='Largest total size one bulk download may reach. '
             'Set 0 to allow archives of any size.')

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res['attachment_bulk_download_max_mb'] = \
            self.env['attachment.bulk.download.wizard']._abd_max_mb()
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            PARAM_MAX_MB, str(max(self.attachment_bulk_download_max_mb, 0)))
