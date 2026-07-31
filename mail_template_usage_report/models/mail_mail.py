# -*- coding: utf-8 -*-
# Part of mail_template_usage_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import api, fields, models


class MailMail(models.Model):
    _inherit = 'mail.mail'

    # No `groups=` on purpose: ordinary users create these rows whenever they
    # send a templated email, and a group-restricted field would make their
    # own create() fail on the access check.
    mail_template_id = fields.Many2one(
        'mail.template', string='Source Email Template', readonly=True,
        ondelete='set null', index=True, copy=False,
        help="Email template this outgoing mail was produced from. Filled in "
             "by the Email Template Usage Report module; empty for mails that "
             "were not built from a template, and for mails created before "
             "that module was installed.")

    @api.model_create_multi
    def create(self, vals_list):
        template_id = self.env.context.get('mtur_template_id')
        if template_id:
            for vals in vals_list:
                vals.setdefault('mail_template_id', template_id)
        # Counting happens in mail.message.create(): every fresh mail.mail
        # creates exactly one delegated mail.message, so counting here as well
        # would double every send.
        return super(MailMail, self).create(vals_list)
