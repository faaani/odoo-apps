# -*- coding: utf-8 -*-
# Part of mail_template_usage_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

USAGE_FIELDS = ('mtur_send_count', 'mtur_first_used', 'mtur_last_used')


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    # Why these columns exist at all
    # ------------------------------
    # Odoo core keeps NO link between a sent email and the template that
    # produced it: neither mail.mail nor mail.message has a template field on
    # 14.0-19.0 (checked, not assumed). This module adds that link, but a
    # stored link alone is not enough: mail.template.auto_delete defaults to
    # True and mail.mail.unlink() cascades onto its mail.message, so the most
    # heavily used templates erase their own evidence seconds after sending.
    # These counters are therefore stamped when the message is created, before
    # anything can delete it. They only ever count sends that happened after
    # this module was installed - the report says so explicitly.
    mtur_send_count = fields.Integer(
        string='Emails Produced', readonly=True, copy=False, default=0,
        help="How many emails/messages were produced from this template since "
             "the Email Template Usage Report module was installed. Sends that "
             "happened before that cannot be counted: Odoo keeps no record of "
             "which template an email came from.")
    mtur_first_used = fields.Datetime(
        string='First Used', readonly=True, copy=False,
        help="First send recorded for this template, i.e. when usage tracking "
             "actually started to see it.")
    mtur_last_used = fields.Datetime(
        string='Last Used', readonly=True, copy=False,
        help="Most recent send recorded for this template.")

    # ------------------------------------------------------------------
    # Usage tracking
    # ------------------------------------------------------------------
    def _mtur_tracked(self):
        """Return ``self`` carrying the context key that makes every mail and
        message created downstream point back to this template."""
        if len(self) != 1 or self.env.context.get('mtur_template_id') == self.id:
            return self
        return self.with_context(mtur_template_id=self.id)

    @api.model
    def _mtur_register_use(self, counts):
        """Record ``{template_id: number_of_new_messages}`` on the templates.

        Written in raw SQL on purpose: going through ``write()`` would move
        ``mail.template.write_date`` on every single send and destroy the
        "customised since installation" signal the whole report is built on.
        Templates are updated in ascending id order so two senders working on
        the same pair of templates cannot deadlock, and the whole thing sits in
        a savepoint: statistics must never be the reason an email fails.
        """
        if not counts:
            return
        template_ids = sorted(counts)
        now = fields.Datetime.now()
        try:
            with self.env.cr.savepoint():
                for template_id in template_ids:
                    self.env.cr.execute("""
                        UPDATE mail_template
                           SET mtur_send_count = COALESCE(mtur_send_count, 0) + %s,
                               mtur_first_used = LEAST(mtur_first_used, %s),
                               mtur_last_used = GREATEST(mtur_last_used, %s)
                         WHERE id = %s
                    """, (counts[template_id], now, now, template_id))
        except Exception:  # pylint: disable=broad-except
            # Never let a statistics update break a send.
            _logger.warning(
                "mail_template_usage_report: could not record usage for templates %s",
                template_ids, exc_info=True)
            return
        # The rows were changed behind the ORM's back.
        templates = self.browse(template_ids)
        if hasattr(templates, 'invalidate_recordset'):
            templates.invalidate_recordset(USAGE_FIELDS)
        else:  # Odoo 14.0 / 15.0
            templates.invalidate_cache(list(USAGE_FIELDS), templates.ids)

    # ------------------------------------------------------------------
    # Send entry points
    # ------------------------------------------------------------------
    def send_mail(self, *args, **kwargs):
        return super(MailTemplate, self._mtur_tracked()).send_mail(*args, **kwargs)
