# -*- coding: utf-8 -*-
# Part of user_access_expiry. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)

PARAM_NOTIFY_ADMINS = 'user_access_expiry.notify_admins'


class ResUsers(models.Model):
    _inherit = 'res.users'

    access_expiry_date = fields.Date(
        string='Access Expiry Date',
        copy=False,
        help='The account is archived automatically once this date has passed. '
             'Leave empty for permanent access.',
    )
    deactivated_by_expiry = fields.Boolean(
        string='Deactivated by Expiry',
        default=False,
        readonly=True,
        copy=False,
        help='Set when this user was archived because the access expiry date passed.',
    )
    expiry_deactivation_date = fields.Datetime(
        string='Expiry Deactivation Date',
        readonly=True,
        copy=False,
        help='When the expiry cron archived this account.',
    )

    def write(self, vals):
        # Re-activating an expired user clears the audit flags and a stale
        # (already-past) expiry date, otherwise the cron re-archives them the
        # next night without anyone noticing.
        res = super(ResUsers, self).write(vals)
        if vals.get('active'):
            today = fields.Date.context_today(self)
            flagged = self.filtered('deactivated_by_expiry')
            if flagged:
                clear = {'deactivated_by_expiry': False, 'expiry_deactivation_date': False}
                stale = flagged.filtered(
                    lambda u: u.access_expiry_date and u.access_expiry_date <= today)
                fresh = flagged - stale
                if stale:
                    super(ResUsers, stale).write(dict(clear, access_expiry_date=False))
                    _logger.info(
                        'Cleared past expiry date on re-activated user(s): %s',
                        ', '.join(stale.mapped('login')))
                if fresh:
                    super(ResUsers, fresh).write(clear)
        return res

    @api.model
    def _expiry_candidates(self):
        today = fields.Date.context_today(self)
        admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
        users = self.search([
            ('active', '=', True),
            ('access_expiry_date', '!=', False),
            ('access_expiry_date', '<=', today),
            ('id', '!=', SUPERUSER_ID),
        ])
        return users.filtered(
            lambda u: not (admin_user and u.id == admin_user.id)
            and not u.has_group('base.group_system'))

    @api.model
    def _cron_deactivate_expired_users(self):
        """Archive users whose access expiry date has passed. Returns logins."""
        archived = []
        now = fields.Datetime.now()
        for user in self._expiry_candidates():
            try:
                with self.env.cr.savepoint():
                    user.write({
                        'active': False,
                        'deactivated_by_expiry': True,
                        'expiry_deactivation_date': now,
                    })
                archived.append(user.login)
                _logger.info('User %r archived: access expired on %s.',
                             user.login, user.access_expiry_date)
            except Exception:  # noqa: BLE001 — one bad record must not abort the run
                _logger.exception('Could not archive expired user %r.', user.login)
        notify = self.env['ir.config_parameter'].sudo().get_param(
            PARAM_NOTIFY_ADMINS, 'True') == 'True'
        if archived and notify:
            self._expiry_notify_admins(archived)
        return archived

    @api.model
    def _expiry_notify_admins(self, archived_logins):
        try:
            admins = self.search([
                ('active', '=', True),
                ('share', '=', False),
            ]).filtered(lambda u: u.has_group('base.group_system') and u.email)
            if not admins:
                return
            body = _(
                '%(count)s user account(s) were archived because their access '
                'expiry date passed:'
            ) % {'count': len(archived_logins)}
            items = ''.join('<li>%s</li>' % html_escape(login) for login in archived_logins)
            self.env['mail.mail'].sudo().create({
                'subject': _('Expired users deactivated'),
                'email_to': ','.join(admins.mapped('email')),
                'auto_delete': True,
                'body_html': '<p>%s</p><ul>%s</ul>' % (body, items),
            }).send(raise_exception=False)
        except Exception:  # noqa: BLE001 — notification failure must not fail the cron
            _logger.exception('Expiry admin notification failed.')
