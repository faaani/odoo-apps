# -*- coding: utf-8 -*-
# Part of mail_template_usage_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    # 14.0 sends from send_mail(); the method was renamed to _action_send_mail
    # in 15.0, which is what the other series of this module override.
    def send_mail(self, *args, **kwargs):
        """Attribute composer sends (chatter "Send message" and mass mailing
        from an Action menu) to the template picked in the composer.

        The composer does not go through mail.template.send_mail(): in comment
        mode it calls message_post() on the record and in mass-mail mode it
        creates mail.mail rows itself, so the template has to be pinned here.
        """
        records = self
        if len(self) == 1 and self.template_id:
            records = self.with_context(mtur_template_id=self.template_id.id)
        return super(MailComposeMessage, records).send_mail(*args, **kwargs)
