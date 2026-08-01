# -*- coding: utf-8 -*-
# Part of partner_bank_change_alert. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

from .res_partner_bank import PARAM_ENABLED, PARAM_GROUP_ID


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # explicit get/set: a default-True Boolean bound with config_parameter=
    # could never be switched off (get_param returns the default for any
    # falsy stored value)
    bank_alert_enabled = fields.Boolean(
        string='Bank Account Change Alerts',
        help='Post an audit message on the partner chatter and notify the '
             'alert group whenever a bank account is added, modified or '
             'removed. Account numbers are always masked to the last 4 '
             'characters.')
    bank_alert_group_id = fields.Many2one(
        'res.groups', string='Alert Group',
        help='Members of this group are notified of every partner bank '
             'account change. Empty means the default: the accounting '
             'managers when accounting is installed, otherwise the Settings '
             'administrators.')

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        bank_model = self.env['res.partner.bank']
        res.update(
            bank_alert_enabled=bank_model._bank_alert_config()['enabled'],
            # show the STORED group, not the resolved default: otherwise the
            # first Settings save would pin the dynamic default forever
            bank_alert_group_id=bank_model._bank_alert_stored_group_id() or False,
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PARAM_ENABLED, str(bool(self.bank_alert_enabled)))
        # 0 = "use the dynamic default group"
        icp.set_param(PARAM_GROUP_ID, str(self.bank_alert_group_id.id or 0))
