# -*- coding: utf-8 -*-
# Part of keep_sent_email_history. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

from .mail_mail import PARAM_ENABLED, PARAM_RETENTION_DAYS


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Explicit get/set instead of config_parameter=: the enabled flag defaults to
    # True (set_param(False) would unlink the key and it would flip back on), and
    # retention 0 (= keep forever) is falsy and would be unlinked the same way.
    keep_email_history = fields.Boolean(
        string='Keep Sent Email History',
        help='Keep notification and template emails after sending instead of '
             'letting Odoo delete them.',
    )
    keep_email_history_days = fields.Integer(
        string='Email Retention (days)',
        help='Kept emails older than this many days are deleted by a daily job. '
             'Set 0 to keep them forever.',
    )

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        config = self.env['mail.mail']._keep_history_config()
        res.update(
            keep_email_history=config['enabled'],
            keep_email_history_days=config['days'],
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PARAM_ENABLED, str(bool(self.keep_email_history)))
        icp.set_param(PARAM_RETENTION_DAYS, str(max(self.keep_email_history_days, 0)))
