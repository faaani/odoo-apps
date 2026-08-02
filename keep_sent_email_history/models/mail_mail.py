# -*- coding: utf-8 -*-
# Part of keep_sent_email_history. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

PARAM_ENABLED = 'keep_sent_email_history.enabled'
PARAM_RETENTION_DAYS = 'keep_sent_email_history.retention_days'
DEFAULT_RETENTION_DAYS = 365

# Mail bound to these models carries credentials (password reset, signup and
# portal invitations with live login-token URLs) and must never be retained.
CREDENTIAL_MODELS = ('res.users', 'portal.wizard.user')
# Defensive net: any body containing a signup/reset token URL is credential
# mail regardless of which model it was rendered for.
TOKEN_URL_MARKERS = ('/web/signup', '/web/reset_password')


class MailMail(models.Model):
    _inherit = 'mail.mail'

    kept_by_history = fields.Boolean(
        string='Kept by Email History',
        default=False,
        readonly=True,
        copy=False,
        index=True,
        help='This email was scheduled for deletion after sending, but was kept '
             'by the Keep Sent Email History module.',
    )

    @api.model
    def _keep_history_config(self):
        icp = self.env['ir.config_parameter'].sudo()
        try:
            days = int(icp.get_param(PARAM_RETENTION_DAYS, DEFAULT_RETENTION_DAYS))
        except (TypeError, ValueError):
            days = DEFAULT_RETENTION_DAYS
        return {
            'enabled': icp.get_param(PARAM_ENABLED, 'True') == 'True',
            'days': max(days, 0),  # 0 = keep forever
        }

    @api.model
    def _keep_history_skip(self, vals):
        """Never keep credential-bearing emails: password resets and signup
        invitations (model res.users) and portal invitations (model
        portal.wizard.user) contain login-token URLs — portal signup tokens
        never expire — that core Odoo deliberately deletes after sending.
        As a defensive net, any mail whose body carries a signup/reset URL
        is skipped too, whatever model it was rendered for."""
        if vals.get('model') in CREDENTIAL_MODELS:
            return True
        body = '%s %s' % (vals.get('body_html') or '', vals.get('body') or '')
        return any(marker in body for marker in TOKEN_URL_MARKERS)

    @api.model_create_multi
    def create(self, vals_list):
        config = self._keep_history_config()
        if config['enabled']:
            for vals in vals_list:
                if vals.get('auto_delete') and not self._keep_history_skip(vals):
                    vals['auto_delete'] = False
                    vals['kept_by_history'] = True
        return super(MailMail, self).create(vals_list)

    def write(self, vals):
        # some flows flip auto_delete on after creation (e.g. template resend)
        if vals.get('auto_delete') and self._keep_history_config()['enabled']:
            keep = self.filtered(lambda m: not self._keep_history_skip({
                'model': m.model,
                'body_html': m.body_html,
                'body': m.body,
            }))
            if keep:
                super(MailMail, keep).write(
                    dict(vals, auto_delete=False, kept_by_history=True))
            skipped = self - keep
            return super(MailMail, skipped).write(vals) if skipped else True
        return super(MailMail, self).write(vals)

    @api.model
    def _cron_purge_kept_emails(self, batch=5000, max_batches=20):
        """Delete kept emails older than the retention period. Returns count.

        Terminal states only ('sent', 'exception', 'cancel') — pending mail is
        never touched. Loops up to max_batches per run so a large backlog
        drains in days, not months, while each run stays bounded.
        """
        config = self._keep_history_config()
        if not config['days']:
            return 0
        cutoff = fields.Datetime.now() - timedelta(days=config['days'])
        domain = [
            ('kept_by_history', '=', True),
            ('state', 'in', ('sent', 'exception', 'cancel')),
            ('write_date', '<', cutoff),
        ]
        total = 0
        for _i in range(max_batches):
            mails = self.sudo().search(domain, limit=batch)
            if not mails:
                break
            total += len(mails)
            mails.unlink()
            if len(mails) < batch:
                break
        if total:
            _logger.info('Email history: purged %s email(s) older than %s days.',
                         total, config['days'])
        return total
