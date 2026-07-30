# -*- coding: utf-8 -*-
# Part of user_access_expiry. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

from .res_users import PARAM_NOTIFY_ADMINS


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Explicit get/set: default-True Boolean via config_parameter can never be
    # switched off (set_param(False) unlinks the key and the default wins again).
    expiry_notify_admins = fields.Boolean(
        string='Notify on Access Expiry',
        help='Send Settings administrators an email summary whenever expired '
             'user accounts are archived.',
    )

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        icp = self.env['ir.config_parameter'].sudo()
        res['expiry_notify_admins'] = icp.get_param(PARAM_NOTIFY_ADMINS, 'True') == 'True'
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PARAM_NOTIFY_ADMINS, str(bool(self.expiry_notify_admins)))
