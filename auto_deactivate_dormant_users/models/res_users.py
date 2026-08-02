# -*- coding: utf-8 -*-
# Part of auto_deactivate_dormant_users. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
from datetime import timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)

PARAM_ENABLED = 'auto_deactivate_dormant_users.enabled'
PARAM_DAYS = 'auto_deactivate_dormant_users.days'
PARAM_INCLUDE_NEVER_LOGGED = 'auto_deactivate_dormant_users.include_never_logged'
PARAM_NOTIFY_ADMINS = 'auto_deactivate_dormant_users.notify_admins'
MIN_DAYS = 7
DEFAULT_DAYS = 90


class ResUsers(models.Model):
    _inherit = 'res.users'

    dormancy_exempt = fields.Boolean(
        string='Never Deactivate Automatically',
        default=False,
        help='Exclude this user from automatic dormancy deactivation.',
    )
    deactivated_by_dormancy = fields.Boolean(
        string='Deactivated by Dormancy',
        default=False,
        readonly=True,
        copy=False,
        help='Set when this user was archived by the dormant-user cron.',
    )
    dormancy_deactivation_date = fields.Datetime(
        string='Dormancy Deactivation Date',
        readonly=True,
        copy=False,
        help='When the dormant-user cron archived this account.',
    )

    def write(self, vals):
        # Re-activating a user clears the dormancy audit flags so the next
        # dormancy period is counted from fresh activity, not the old one.
        res = super(ResUsers, self).write(vals)
        if vals.get('active'):
            flagged = self.filtered('deactivated_by_dormancy')
            if flagged:
                super(ResUsers, flagged).write({
                    'deactivated_by_dormancy': False,
                    'dormancy_deactivation_date': False,
                })
        return res

    @api.model
    def _dormancy_get_config(self):
        icp = self.env['ir.config_parameter'].sudo()
        try:
            days = int(icp.get_param(PARAM_DAYS, DEFAULT_DAYS))
        except (TypeError, ValueError):
            days = DEFAULT_DAYS
        return {
            'enabled': icp.get_param(PARAM_ENABLED, 'False') == 'True',
            'days': max(days, MIN_DAYS),
            'include_never_logged': icp.get_param(PARAM_INCLUDE_NEVER_LOGGED, 'False') == 'True',
            'notify_admins': icp.get_param(PARAM_NOTIFY_ADMINS, 'True') == 'True',
        }

    @api.model
    def _dormancy_candidates(self, config):
        """Active internal users past the dormancy threshold, guards applied.

        login_date is a related (non-stored) field over log_ids, so latest-login
        comparison is done in Python: a search domain on the related path would
        match ANY old login row, not the latest one.
        """
        threshold = fields.Datetime.now() - timedelta(days=config['days'])
        admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
        users = self.search([
            ('active', '=', True),
            ('share', '=', False),
            ('dormancy_exempt', '=', False),
            ('id', '!=', SUPERUSER_ID),
        ])
        candidates = self.browse()
        for user in users:
            if admin_user and user.id == admin_user.id:
                continue
            if user.has_group('base.group_system'):
                continue
            last_seen = user.login_date
            if not last_seen:
                if not config['include_never_logged']:
                    continue
                last_seen = user.create_date
            if last_seen and last_seen < threshold:
                candidates |= user
        return candidates

    @api.model
    def _cron_deactivate_dormant_users(self):
        """Archive dormant users. Returns the list of archived logins."""
        config = self._dormancy_get_config()
        if not config['enabled']:
            return []
        candidates = self._dormancy_candidates(config)
        archived = []
        now = fields.Datetime.now()
        for user in candidates:
            try:
                # savepoint: a failed write (e.g. constraint from another module
                # inheriting res.users) must not poison the cursor for the rest
                with self.env.cr.savepoint():
                    user.write({
                        'active': False,
                        'deactivated_by_dormancy': True,
                        'dormancy_deactivation_date': now,
                    })
                archived.append(user.login)
                _logger.info(
                    'Dormant user %r archived (no login for %s+ days).',
                    user.login, config['days'],
                )
            except Exception:  # noqa: BLE001 — one bad record must not abort the run
                _logger.exception('Could not archive dormant user %r.', user.login)
        if archived and config['notify_admins']:
            self._dormancy_notify_admins(archived, config['days'])
        return archived

    @api.model
    def _dormancy_notify_admins(self, archived_logins, days):
        try:
            admins = self.search([
                ('active', '=', True),
                ('share', '=', False),
            ]).filtered(lambda u: u.has_group('base.group_system') and u.email)
            if not admins:
                return
            # %-interpolation after _() — the in-call kwargs form only exists on 16.0+
            body = _(
                '%(count)s user account(s) were automatically archived after '
                '%(days)s days without login:'
            ) % {'count': len(archived_logins), 'days': days}
            items = ''.join('<li>%s</li>' % html_escape(login) for login in archived_logins)
            # savepoint: the archiving writes above must survive a DB-level
            # failure here — without it a failed mail INSERT poisons the
            # transaction and the whole run rolls back at commit, which the
            # try/except alone cannot prevent.
            with self.env.cr.savepoint():
                self.env['mail.mail'].sudo().create({
                    'subject': _('Dormant users deactivated'),
                    'email_to': ','.join(admins.mapped('email')),
                    'auto_delete': True,
                    'body_html': '<p>%s</p><ul>%s</ul>' % (body, items),
                }).send(raise_exception=False)
        except Exception:  # noqa: BLE001 — notification failure must not fail the cron
            _logger.exception('Dormancy admin notification failed.')
