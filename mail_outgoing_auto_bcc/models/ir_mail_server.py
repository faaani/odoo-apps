# -*- coding: utf-8 -*-
# Part of mail_outgoing_auto_bcc. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import models, tools

_logger = logging.getLogger(__name__)

# Per-company ir.config_parameter keys. Text parameters must be read/written
# explicitly (get_values/set_values): binding them with config_parameter=
# would re-serve the field default whenever the stored value is falsy, so an
# emptied setting could never be saved.
PARAM_CC = 'mail_outgoing_auto_bcc.cc.%d'
PARAM_BCC = 'mail_outgoing_auto_bcc.bcc.%d'


def _parse_address_list(raw):
    """Split a comma-separated address list leniently.

    Whitespace and empty tokens are dropped; tokens that do not normalize to
    a valid email address are ignored so a malformed setting can never break
    sending. Returned addresses are normalized (lowercased) and unique.
    """
    result = []
    for token in (raw or '').split(','):
        normalized = tools.email_normalize(token.strip())
        if normalized and normalized not in result:
            result.append(normalized)
    return result


class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    def _auto_copy_lists(self):
        """Return (cc_list, bcc_list) configured for the mail being sent.

        ``mail.mail._send`` resolves the effective company PER MAIL (from the
        mail's author) and passes it down through the
        ``mail_auto_copy_company_id`` context key, so queue-cron flushes in a
        multi-company database never apply one company's copy addresses to
        another company's mail. The key set to 0 means "never copy this mail"
        (security-sensitive mail such as password resets). Only mail sent
        outside the mail.mail stack falls back to ``self.env.company``.
        """
        ctx_company_id = self.env.context.get('mail_auto_copy_company_id')
        if ctx_company_id == 0:
            return [], []
        company_id = ctx_company_id or self.env.company.id
        icp = self.env['ir.config_parameter'].sudo()
        return (
            _parse_address_list(icp.get_param(PARAM_CC % company_id)),
            _parse_address_list(icp.get_param(PARAM_BCC % company_id)),
        )

    def send_email(self, message, *args, **kwargs):
        """Append the configured automatic CC / BCC to the outgoing message.

        Hooking the lowest common send point means every email leaving
        through Odoo's mail stack gets the copy: chatter notifications,
        composer mail, templates and the mail queue alike. Any failure while
        applying the copy is logged and the message is sent unchanged -
        this module must never break outgoing mail.
        """
        record = self
        try:
            record = self._auto_copy_apply(message)
        except Exception:
            _logger.exception(
                "mail_outgoing_auto_bcc: could not apply the automatic "
                "copy; sending the message unchanged")
        return super(IrMailServer, record).send_email(message, *args, **kwargs)

    def _auto_copy_apply(self, message):
        """Add configured addresses to the Cc / Bcc headers of ``message``.

        Addresses already present in To / Cc / Bcc are skipped
        (case-insensitive). Returns the recordset to run ``send_email`` on:
        when the caller restricted deliverable recipients through the
        ``send_validated_to`` context (mail.mail does since 16.0), the added
        addresses are appended to it, otherwise they would be silently
        dropped from the SMTP envelope.
        """
        cc_conf, bcc_conf = self._auto_copy_lists()
        if not cc_conf and not bcc_conf:
            return self  # fast path: feature not configured, zero overhead

        existing = set()
        for header in ('To', 'Cc', 'Bcc'):
            for addr in tools.email_split(str(message[header] or '')):
                existing.add((tools.email_normalize(addr) or addr).lower())

        added = []

        def _new_addresses(configured):
            fresh = []
            for addr in configured:
                if addr not in existing:
                    existing.add(addr)
                    fresh.append(addr)
                    added.append(addr)
            return fresh

        new_cc = _new_addresses(cc_conf)
        new_bcc = _new_addresses(bcc_conf)
        if new_cc:
            self._auto_copy_extend_header(message, 'Cc', new_cc)
        if new_bcc:
            self._auto_copy_extend_header(message, 'Bcc', new_bcc)

        validated_to = self.env.context.get('send_validated_to')
        if added and validated_to:
            return self.with_context(
                send_validated_to=list(validated_to) + added)
        return self

    @staticmethod
    def _auto_copy_extend_header(message, name, addresses):
        """Merge ``addresses`` into the ``name`` header of ``message``."""
        current = str(message[name] or '')
        del message[name]
        joined = ', '.join(addresses)
        message[name] = '%s, %s' % (current, joined) if current else joined
