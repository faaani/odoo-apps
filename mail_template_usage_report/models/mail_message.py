# -*- coding: utf-8 -*-
# Part of mail_template_usage_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import api, fields, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    # No `groups=` on purpose: ordinary users create messages, and a
    # group-restricted field would make their own create() fail.
    mail_template_id = fields.Many2one(
        'mail.template', string='Source Email Template', readonly=True,
        ondelete='set null', index='btree_not_null', copy=False,
        help="Email template this message was produced from. Filled in by the "
             "Email Template Usage Report module; empty for messages that were "
             "not built from a template, and for messages created before that "
             "module was installed.")

    @api.model_create_multi
    def create(self, vals_list):
        template_id = self.env.context.get('mtur_template_id')
        if template_id:
            for vals in vals_list:
                vals.setdefault('mail_template_id', template_id)
        counts = {}
        for vals in vals_list:
            source = vals.get('mail_template_id')
            if source:
                counts[source] = counts.get(source, 0) + 1
        # mail.message.create() is one of the hottest paths in Odoo: when no
        # template is involved (log notes, tracking, discuss) nothing above
        # touched vals_list and nothing below runs.
        messages = super(MailMessage, self).create(vals_list)
        if counts:
            self.env['mail.template']._mtur_register_use(counts)
        return messages
