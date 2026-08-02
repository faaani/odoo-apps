# -*- coding: utf-8 -*-
# Part of mail_autofollow_optout. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _autofollow_optout_partners(self, partner_ids):
        """Drop partners whose user opted out of automatic following."""
        if not partner_ids:
            return partner_ids
        opted_out = self.env['res.users'].sudo().search([
            ('partner_id', 'in', list(partner_ids)),
            ('no_auto_follow', '=', True),
        ]).mapped('partner_id').ids
        if not opted_out:
            return partner_ids
        return [pid for pid in partner_ids if pid not in opted_out]

    def _autofollow_is_manual(self, partner_ids):
        """A deliberate follow is the user subscribing themselves (the Follow
        button). The other deliberate path — the Add Followers invite wizard —
        sets mail_manual_subscribe in the context itself (see
        mail_wizard_invite.py). Anything else — assignment, creation,
        tracked-field subscription — is automatic and honours the
        preference."""
        own = self.env.user.partner_id.id
        return bool(partner_ids) and set(partner_ids) == {own}

    # Fully signature-agnostic: the parameters of these hooks differ per series
    # (14.0 has channel_ids as its SECOND positional argument), so nothing is
    # ever re-bound by position here.
    def message_subscribe(self, *args, **kwargs):
        partner_ids = args[0] if args else kwargs.get('partner_ids')
        record = self
        if self._autofollow_is_manual(partner_ids):
            record = self.with_context(mail_manual_subscribe=True)
        return super(MailThread, record).message_subscribe(*args, **kwargs)

    def _message_subscribe(self, *args, **kwargs):
        if self.env.context.get('mail_manual_subscribe'):
            return super(MailThread, self)._message_subscribe(*args, **kwargs)
        try:
            if args and args[0]:
                args = (self._autofollow_optout_partners(args[0]),) + args[1:]
            elif kwargs.get('partner_ids'):
                kwargs = dict(kwargs, partner_ids=self._autofollow_optout_partners(
                    kwargs['partner_ids']))
        except Exception:  # noqa: BLE001 — never break posting over a preference
            _logger.exception('mail_autofollow_optout: filtering failed.')
        return super(MailThread, self)._message_subscribe(*args, **kwargs)
