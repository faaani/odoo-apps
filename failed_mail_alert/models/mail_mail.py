# -*- coding: utf-8 -*-
# Part of failed_mail_alert. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)

PARAM_ENABLED = 'failed_mail_alert.enabled'
PARAM_THRESHOLD = 'failed_mail_alert.threshold'
PARAM_AGE_MINUTES = 'failed_mail_alert.age_minutes'
PARAM_LAST_ALERT = 'failed_mail_alert.last_alert'

DEFAULT_THRESHOLD = 5
DEFAULT_AGE_MINUTES = 60
MIN_THRESHOLD = 1
MIN_AGE_MINUTES = 5
REALERT_HOURS = 24
MAX_DETAIL_ROWS = 20
# 'outgoing' is included on purpose: a dead SMTP connection leaves messages
# queued forever without ever reaching the 'exception' state.
STUCK_STATES = ['exception', 'outgoing']


def int_param(value, default):
    """int() of a stored system parameter, falling back to *default* on garbage.

    Module level because two callers need different post-processing: the
    settings screen wants the exact stored number (0 included) while the
    watchdog wants it clamped to a sane floor.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class MailMail(models.Model):
    _inherit = 'mail.mail'

    failed_alert_notice = fields.Boolean(
        string='Queue Alert Notice',
        default=False,
        readonly=True,
        copy=False,
        help='Set on the alert messages produced by Failed Email Alerts, so the '
             'watchdog never counts its own (also undeliverable) emails as '
             'evidence that the queue is broken.',
    )

    @api.model
    def _failed_alert_config(self):
        """Effective watchdog configuration, clamped to safe values."""
        icp = self.env['ir.config_parameter'].sudo()
        # get_param() returns its default for ANY falsy stored value, so the
        # switch and the numbers are stored as explicit 'True'/'False'/'0'
        # strings by res.config.settings and parsed back here. Binding them
        # with config_parameter= would make "off" and "0" unsaveable.
        threshold = int_param(icp.get_param(PARAM_THRESHOLD, DEFAULT_THRESHOLD),
                              DEFAULT_THRESHOLD)
        age = int_param(icp.get_param(PARAM_AGE_MINUTES, DEFAULT_AGE_MINUTES),
                        DEFAULT_AGE_MINUTES)
        return {
            'enabled': icp.get_param(PARAM_ENABLED, 'True') == 'True',
            'threshold': max(threshold, MIN_THRESHOLD),
            'age_minutes': max(age, MIN_AGE_MINUTES),
        }

    @api.model
    def _failed_alert_domain(self, config):
        """Messages that should have left the queue by now and have not."""
        now = fields.Datetime.now()
        cutoff = now - timedelta(minutes=config['age_minutes'])
        return [
            ('state', 'in', STUCK_STATES),
            ('failed_alert_notice', '=', False),
            ('create_date', '<', cutoff),
            # A mail deliberately queued for later is not stuck. This is the
            # exact exclusion mail.mail.process_email_queue() applies, so the
            # watchdog and the sender agree on what "due" means. Comparing a
            # datetime works on both field types (Char <= 15.0, Datetime 16.0+).
            '|', ('scheduled_date', '=', False),
            ('scheduled_date', '<=', now),
        ]

    @api.model
    def _failed_alert_rate_limited(self):
        """True while the previous alert is younger than REALERT_HOURS."""
        last = self.env['ir.config_parameter'].sudo().get_param(PARAM_LAST_ALERT)
        if not last:
            return False
        try:
            last_dt = fields.Datetime.to_datetime(last)
        except (TypeError, ValueError):
            return False  # unreadable stamp: better one extra alert than none
        return bool(last_dt) and last_dt > (
            fields.Datetime.now() - timedelta(hours=REALERT_HOURS))

    @api.model
    def _failed_mail_alert_check(self):
        """Watchdog entry point (scheduled action).

        Returns the number of stuck messages reported, 0 when no alert was
        sent. Never raises: a broken watchdog must not leave the scheduled
        action failing on every run.
        """
        try:
            config = self._failed_alert_config()
            if not config['enabled']:
                return 0
            domain = self._failed_alert_domain(config)
            count = self.sudo().search_count(domain)
            if count < config['threshold']:
                return 0
            if self._failed_alert_rate_limited():
                _logger.info(
                    'Failed email alert: %s message(s) still stuck, but an alert '
                    'was already sent within the last %s hours.',
                    count, REALERT_HOURS)
                return 0
            sample = self.sudo().search(domain, order='create_date asc',
                                        limit=MAX_DETAIL_ROWS)
            if not self._failed_alert_notify_admins(count, sample, config):
                # no alert was even built — do not burn the 24h window on it
                return 0
            self.env['ir.config_parameter'].sudo().set_param(
                PARAM_LAST_ALERT, fields.Datetime.to_string(fields.Datetime.now()))
            _logger.warning(
                'Failed email alert: %s outgoing message(s) have been stuck for '
                'more than %s minutes; an alert was raised for the administrators.',
                count, config['age_minutes'])
            return count
        except Exception:  # noqa: BLE001 — the watchdog must never break its cron
            _logger.exception('Failed email alert check failed.')
            return 0

    @api.model
    def _failed_alert_summary_rows(self, sample):
        """One escaped HTML table row per stuck message."""
        rows = []
        for mail in sample:
            recipients = mail.email_to or ', '.join(
                [email for email in mail.recipient_ids.mapped('email') if email])
            reason = (mail.failure_reason or '').strip()
            reason = reason.splitlines()[0] if reason else _('Still queued, never sent')
            rows.append(
                '<tr>'
                '<td style="padding:4px 10px;border-bottom:1px solid #ddd;">%s</td>'
                '<td style="padding:4px 10px;border-bottom:1px solid #ddd;">%s</td>'
                '<td style="padding:4px 10px;border-bottom:1px solid #ddd;">%s</td>'
                '</tr>' % (
                    html_escape(mail.subject or _('(no subject)')),
                    html_escape(recipients or _('(no recipient)')),
                    html_escape(reason[:200]),
                ))
        return ''.join(rows)

    @api.model
    def _failed_alert_notify_admins(self, count, sample, config):
        """Email every Settings administrator.

        Returns True when an alert message was built and handed to the mail
        server, False when there was nobody to warn. Delivery of the alert
        itself can still fail — that is logged, loudly, because it is the one
        failure this module cannot report by email.

        Wrapped end to end: a notification problem must never propagate out of
        the scheduled action.
        """
        try:
            # the group test is per record and rebuilds an environment each
            # time, so let SQL drop everyone who could not be mailed anyway
            admins = self.env['res.users'].sudo().search([
                ('active', '=', True),
                ('share', '=', False),
                ('email', '!=', False),
            ]).filtered(lambda u: u.has_group('base.group_system'))
            if not admins:
                _logger.warning(
                    'Failed email alert: %s stuck message(s) found but no '
                    'administrator has an email address — nobody was notified.',
                    count)
                return False
            # %-interpolation after _(): the in-call kwargs form is 16.0+ only
            body = _(
                '%(count)s outgoing email(s) have been waiting in the Odoo mail '
                'queue for more than %(age)s minutes without being delivered. '
                'Outgoing mail is most likely misconfigured or refused by the '
                'mail server.'
            ) % {'count': count, 'age': config['age_minutes']}
            header = '<tr>%s</tr>' % ''.join(
                '<th align="left" style="padding:4px 10px;">%s</th>' % html_escape(label)
                for label in (_('Subject'), _('Recipient'), _('Error')))
            footer = ''
            if count > MAX_DETAIL_ROWS:
                footer = '<p>%s</p>' % html_escape(_(
                    'Only the %(shown)s oldest of %(count)s stuck messages are '
                    'listed. Open Settings > Technical > Email > Emails for the '
                    'full queue.'
                ) % {'shown': MAX_DETAIL_ROWS, 'count': count})
            # body/footer are translated strings: escape them too, so a
            # third-party .po file cannot inject markup into an admin's inbox
            html = '<p>%s</p><table style="border-collapse:collapse;">%s%s</table>%s' % (
                html_escape(body), header,
                self._failed_alert_summary_rows(sample), footer)
            # auto_delete stays False on purpose: this alert is the audit trail
            # of an outage, and force-sending it may well fail too.
            alert = self.sudo().create({
                'subject': _('Odoo alert: outgoing emails are failing'),
                'email_to': ','.join(admins.mapped('email')),
                'body_html': html,
                'auto_delete': False,
                'failed_alert_notice': True,
            })
            # Force send: the queue cron is exactly what cannot be trusted here,
            # so the alert leaves within this very transaction.
            alert.send(raise_exception=False)
            if alert.state != 'sent':
                # The one failure that cannot be reported by email. Say so in
                # the log rather than claiming the administrators were warned.
                _logger.error(
                    'Failed email alert: the alert itself could not be '
                    'delivered (%s). Outgoing mail is down — check the mail '
                    'server configuration.',
                    alert.failure_reason or alert.state)
            return True
        except Exception:  # noqa: BLE001 — notification failure must not fail the cron
            _logger.exception('Failed email alert notification failed.')
            return False
