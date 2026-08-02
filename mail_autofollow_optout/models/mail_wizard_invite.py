# -*- coding: utf-8 -*-
# Part of mail_autofollow_optout. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import models


class MailWizardInvite(models.TransientModel):
    _inherit = 'mail.wizard.invite'

    def add_followers(self):
        """Adding followers through the invite wizard is a deliberate human
        action, exactly like the Follow button: flag the whole call as a
        manual subscription so the auto-follow opt-out (which only targets
        AUTOMATIC subscriptions) never silently drops the invited partners
        while their invitation email still goes out.

        The flag stays in the context for the whole call, including the
        notification step. Verified safe on 14.0-19.0: the only callers of
        _message_subscribe in mail/models/mail_thread.py are message_post's
        author auto-subscribe and message_subscribe itself, so nothing in the
        notify path can silently consume this flag."""
        return super(
            MailWizardInvite,
            self.with_context(mail_manual_subscribe=True),
        ).add_followers()
