# -*- coding: utf-8 -*-
# Part of cron_watchdog_alert. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.tools import html_escape, str2bool

_logger = logging.getLogger(__name__)

PARAM_ENABLED = 'cron_watchdog_alert.enabled'
PARAM_LAG_MINUTES = 'cron_watchdog_alert.lag_minutes'
PARAM_LAST_WEB_CHECK = 'cron_watchdog_alert.last_web_check'
DEFAULT_LAG_MINUTES = 60
MIN_LAG_MINUTES = 15
REALERT_HOURS = 24
WEB_CHECK_EVERY_MINUTES = 15


class IrCron(models.Model):
    _inherit = 'ir.cron'

    watchdog_exempt = fields.Boolean(
        string='Exclude from Watchdog',
        default=False,
        help='Do not alert administrators when this scheduled action is overdue.',
    )
    watchdog_last_alert = fields.Datetime(
        string='Last Watchdog Alert',
        readonly=True,
        copy=False,
    )

    @api.model
    def _watchdog_config(self):
        icp = self.env['ir.config_parameter'].sudo()
        try:
            enabled = str2bool(icp.get_param(PARAM_ENABLED, 'True'))
        except ValueError:
            enabled = True
        try:
            lag = int(icp.get_param(PARAM_LAG_MINUTES, DEFAULT_LAG_MINUTES))
        except (TypeError, ValueError):
            lag = DEFAULT_LAG_MINUTES
        return {'enabled': enabled, 'lag_minutes': max(lag, MIN_LAG_MINUTES)}

    @api.model
    def _watchdog_stale_crons(self, config):
        """Active, non-exempt crons whose nextcall is further in the past than
        the lag threshold — they should have run by now and have not."""
        now = fields.Datetime.now()
        cutoff = now - timedelta(minutes=config['lag_minutes'])
        realert_cutoff = now - timedelta(hours=REALERT_HOURS)
        watchdog = self.env.ref('cron_watchdog_alert.ir_cron_watchdog',
                                raise_if_not_found=False)
        stale = self.sudo().search([
            ('active', '=', True),
            ('watchdog_exempt', '=', False),
            ('nextcall', '<', cutoff),
        ])
        if watchdog:
            stale = stale - watchdog  # it reports on the others, not itself
        # rate limit: one alert per cron per REALERT_HOURS
        stale = stale.filtered(
            lambda c: not c.watchdog_last_alert
            or c.watchdog_last_alert < realert_cutoff)
        if stale:
            # The scheduler row-locks a job for its whole run: a locked row is a
            # long-RUNNING job, not a stalled one — and writing to it from a web
            # request would hang the page load until the job ends. SKIP LOCKED
            # both avoids that hang and kills the false positive.
            self.env.cr.execute(
                "SELECT id FROM ir_cron WHERE id = ANY(%s) "
                "FOR NO KEY UPDATE SKIP LOCKED", (stale.ids,))
            lockable = {row[0] for row in self.env.cr.fetchall()}
            stale = stale.filtered(lambda c: c.id in lockable)
        return stale

    @api.model
    def _watchdog_check(self, source='cron'):
        """Find overdue scheduled actions and alert administrators.

        Returns the list of alerted cron names. Never raises: this is called
        from web requests too, where a watchdog problem must not break Odoo.
        """
        try:
            config = self._watchdog_config()
            if not config['enabled']:
                return []
            stale = self._watchdog_stale_crons(config)
            if not stale:
                return []
            self._watchdog_notify_admins(stale, config, source)
            stale.sudo().write({'watchdog_last_alert': fields.Datetime.now()})
            for cron in stale:
                _logger.warning(
                    'Cron watchdog: %r is overdue (nextcall %s, source: %s).',
                    cron.name, cron.nextcall, source)
            return stale.mapped('name')
        except Exception:  # noqa: BLE001 — never break the caller (web request!)
            _logger.exception('Cron watchdog check failed.')
            return []

    @api.model
    def _watchdog_web_tick(self):
        """Throttled watchdog check for web requests. Never raises and never
        leaves the request transaction aborted.

        - Readonly cursors (18.0+ serve session_info from a readonly route on
          replica setups) are skipped entirely: no writes on a ro transaction.
        - The whole tick runs inside a savepoint and flushes before leaving it,
          so flush-time errors (throttle write races included) surface HERE,
          get rolled back to the savepoint, and the request stays healthy.
        """
        try:
            if getattr(self.env.cr, 'readonly', False):
                return False
            with self.env.cr.savepoint():
                icp = self.env['ir.config_parameter'].sudo()
                now = fields.Datetime.now()
                last = icp.get_param(PARAM_LAST_WEB_CHECK)
                due = True
                if last:
                    try:
                        due = fields.Datetime.from_string(last) < (
                            now - timedelta(minutes=WEB_CHECK_EVERY_MINUTES))
                    except ValueError:
                        due = True
                if due:
                    icp.set_param(PARAM_LAST_WEB_CHECK, fields.Datetime.to_string(now))
                    self._watchdog_check(source='web')
                    try:
                        self.env.flush_all()
                    except AttributeError:  # <= 15.0
                        self.flush()
                return due
        except Exception:  # noqa: BLE001 — never break page loads
            _logger.exception('Cron watchdog web tick failed.')
            return False

    @api.model
    def _watchdog_notify_admins(self, stale, config, source):
        admins = self.env['res.users'].sudo().search([
            ('active', '=', True),
            ('share', '=', False),
        ]).filtered(lambda u: u.has_group('base.group_system') and u.email)
        if not admins:
            _logger.warning(
                'Cron watchdog: %s stalled action(s) found but no administrator '
                'has an email address — nobody was notified.', len(stale))
            return
        rows = ''.join(
            '<li><b>%s</b> — should have run at %s</li>' % (
                html_escape(c.name), c.nextcall)
            for c in stale)
        body = _(
            '%(count)s scheduled action(s) look stalled: they were due more '
            'than %(lag)s minutes ago and have not run. The scheduler may be '
            'stopped, stuck on a long job, or the action may be failing.'
        ) % {'count': len(stale), 'lag': config['lag_minutes']}
        # force_send: if the cron worker is dead, the mail queue is dead too —
        # the email must go out within this very transaction/request.
        self.env['mail.mail'].sudo().create({
            'subject': _('Odoo alert: scheduled actions have stopped running'),
            'email_to': ','.join(admins.mapped('email')),
            'auto_delete': True,
            'body_html': '<p>%s</p><ul>%s</ul>' % (body, rows),
        }).send(raise_exception=False)
