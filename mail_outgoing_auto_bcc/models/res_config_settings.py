# -*- coding: utf-8 -*-
# Part of mail_outgoing_auto_bcc. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

from .ir_mail_server import PARAM_BCC, PARAM_CC


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Explicit get_values/set_values on purpose: these are text parameters
    # and config_parameter= would return the field default for any falsy
    # stored value, so clearing the field could never be persisted.
    mail_auto_cc = fields.Char(
        string='Auto CC',
        help='Comma-separated email addresses added as CC to every outgoing '
             'email of this company. Leave empty to disable. Warning: these '
             'mailboxes receive your outgoing mail - treat them as '
             'privileged. Password reset and invitation emails are never '
             'copied.')
    mail_auto_bcc = fields.Char(
        string='Auto BCC',
        help='Comma-separated email addresses added as BCC to every outgoing '
             'email of this company. Leave empty to disable. Warning: these '
             'mailboxes receive your outgoing mail - treat them as '
             'privileged. Password reset and invitation emails are never '
             'copied.')

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        icp = self.env['ir.config_parameter'].sudo()
        company_id = self.env.company.id
        res.update(
            mail_auto_cc=icp.get_param(PARAM_CC % company_id, '') or '',
            mail_auto_bcc=icp.get_param(PARAM_BCC % company_id, '') or '',
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        icp = self.env['ir.config_parameter'].sudo()
        company_id = self.env.company.id
        # set_param deletes the key for an empty value, which is exactly the
        # disabled state read back by get_param(..., '').
        icp.set_param(PARAM_CC % company_id, (self.mail_auto_cc or '').strip())
        icp.set_param(PARAM_BCC % company_id, (self.mail_auto_bcc or '').strip())
