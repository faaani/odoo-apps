# -*- coding: utf-8 -*-
# Part of mail_outgoing_auto_bcc. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import models

# Mail belonging to these models carries security-sensitive content (password
# reset links, signup/invitation tokens) and is never auto-copied.
NEVER_COPY_MODELS = ('res.users',)


class MailMail(models.Model):
    _inherit = 'mail.mail'

    def _auto_copy_company_key(self):
        """Effective company for the auto CC/BCC of this single mail.

        Returns the id of the company whose settings apply, or 0 when the
        mail must never be copied. The author's company (``create_uid``) is
        used so a queue cron running under another company still applies the
        right settings; ``self.env.company`` is only a last resort.
        """
        self.ensure_one()
        if self.model in NEVER_COPY_MODELS:
            return 0
        company = self.create_uid.company_id or self.env.company
        return company.id

    def _send(self, *args, **kwargs):
        """Tag every outgoing batch with its per-mail effective company.

        The context key is read back by ``ir.mail_server._auto_copy_lists``
        at transmission time. Batches mixing several companies are split so
        the resolution stays correct per mail.
        """
        if not self:
            return super(MailMail, self)._send(*args, **kwargs)
        groups = {}
        for mail in self:
            groups.setdefault(mail._auto_copy_company_key(), []).append(mail.id)
        if len(groups) == 1:
            key = next(iter(groups))
            return super(
                MailMail, self.with_context(mail_auto_copy_company_id=key),
            )._send(*args, **kwargs)
        res = True
        for key, ids in groups.items():
            res = super(
                MailMail,
                self.browse(ids).with_context(mail_auto_copy_company_id=key),
            )._send(*args, **kwargs)
        return res
