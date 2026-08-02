# -*- coding: utf-8 -*-
# Part of auth_login_lockout. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
from datetime import timedelta
from html import escape

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

PARAM_ENABLED = 'auth_login_lockout.enabled'
PARAM_MAX_ATTEMPTS = 'auth_login_lockout.max_attempts'
PARAM_LOCK_MINUTES = 'auth_login_lockout.lock_minutes'
PARAM_ALERT = 'auth_login_lockout.alert'
PARAM_RETENTION_DAYS = 'auth_login_lockout.retention_days'

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_LOCK_MINUTES = 15
DEFAULT_RETENTION_DAYS = 30

# a login longer than this is not a real account, only wasted index space
LOGIN_MAX_LEN = 128
IP_MAX_LEN = 64
# rows deleted per batch, and how many batches one purge run may chain, so the
# cron drains a flood without ever holding an unbounded transaction
GC_BATCH = 20000
GC_MAX_BATCHES = 50


def _clamp_int(value, default, minimum):
    """Read an integer config parameter defensively.

    A parameter that was never written, emptied by hand or corrupted must never
    turn the protection into something nonsensical (a lockout after 0 failures
    would lock everybody out immediately).

    ``get_param`` returns the Boolean ``False`` for a key that does not exist,
    and ``int(False)`` is a perfectly valid 0 - so this has to reject non-string
    input explicitly rather than lean on ValueError. Getting this wrong locked
    every account out after a single failure on a fresh install.
    """
    if not isinstance(value, str) or not value.strip():
        return default
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return max(result, minimum)


class AuthLoginAttempt(models.Model):
    _name = 'auth.login.attempt'
    _description = 'Login Attempt'
    _order = 'create_date desc, id desc'
    _rec_name = 'login'

    login = fields.Char(
        string='Login', required=True, index=True, readonly=True,
        help='The login exactly as it was typed, lower-cased.')
    ip = fields.Char(string='IP Address', readonly=True)
    result = fields.Selection([
        ('failed', 'Failed'),
        ('success', 'Successful'),
        ('blocked', 'Blocked - locked out'),
    ], string='Result', required=True, index=True, readonly=True, default='failed')
    released = fields.Boolean(
        string='Released', default=False, readonly=True, copy=False,
        help='A released failure no longer counts towards a lockout. Releasing '
             'is how an administrator lets a locked-out colleague back in '
             'without waiting for the lockout to expire.')

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------
    @api.model
    def _lockout_config(self):
        """Return the effective policy.

        Values are read with explicit string defaults instead of being bound to
        the settings fields with ``config_parameter=``: ``get_param`` hands back
        the default for any falsy stored value, so a Boolean that defaults to
        True could never be switched off.
        """
        icp = self.env['ir.config_parameter'].sudo()
        return {
            'enabled': icp.get_param(PARAM_ENABLED, 'True') == 'True',
            'alert': icp.get_param(PARAM_ALERT, 'False') == 'True',
            'max_attempts': _clamp_int(
                icp.get_param(PARAM_MAX_ATTEMPTS, str(DEFAULT_MAX_ATTEMPTS)),
                DEFAULT_MAX_ATTEMPTS, 1),
            'lock_minutes': _clamp_int(
                icp.get_param(PARAM_LOCK_MINUTES, str(DEFAULT_LOCK_MINUTES)),
                DEFAULT_LOCK_MINUTES, 1),
            'retention_days': _clamp_int(
                icp.get_param(PARAM_RETENTION_DAYS, str(DEFAULT_RETENTION_DAYS)),
                DEFAULT_RETENTION_DAYS, 1),
        }

    @api.model
    def _normalize_login(self, login):
        """Logins are matched case-insensitively.

        Without this, ``Admin`` and ``admin`` would keep separate counters and
        an attacker could multiply the allowance by changing the casing.

        Control characters are dropped as well: this string is unauthenticated
        input that ends up in a mail subject, where an embedded CR/LF would let
        the sender forge headers.
        """
        if not isinstance(login, str):
            return ''
        cleaned = ''.join(ch for ch in login if ch.isprintable())
        return cleaned.strip().lower()[:LOGIN_MAX_LEN]

    @api.model
    def _flush_attempts(self):
        """Make pending attempt rows visible to the next search.

        Odoo 16.0 introduced ``Environment.flush_all``; 14.0 and 15.0 only have
        the recordset-level ``flush``.
        """
        flush_all = getattr(self.env, 'flush_all', None)
        if flush_all is not None:
            flush_all()
        else:
            self.flush()

    # ------------------------------------------------------------------
    # policy
    # ------------------------------------------------------------------
    @api.model
    def _locked_until(self, login):
        """Return when the lockout for ``login`` expires, or None if not locked.

        Reads run as superuser on purpose: this decision is taken before anyone
        is authenticated, so there is no user whose access rights could apply.
        """
        config = self._lockout_config()
        if not config['enabled']:
            return None
        login = self._normalize_login(login)
        if not login:
            # an empty login can never own a lockout, otherwise every blank
            # submission would count towards the same bucket
            return None

        attempts = self.sudo()
        max_attempts = config['max_attempts']
        window = timedelta(minutes=config['lock_minutes'])
        since = fields.Datetime.now() - window

        # a successful login clears the streak, so only failures newer than the
        # last success can lock the account
        last_success = attempts.search(
            [('login', '=', login), ('result', '=', 'success')],
            order='create_date desc', limit=1)
        if last_success and last_success.create_date and last_success.create_date > since:
            since = last_success.create_date

        failures = attempts.search(
            [('login', '=', login), ('result', '=', 'failed'),
             ('released', '=', False), ('create_date', '>', since)],
            order='create_date desc', limit=max_attempts)
        if len(failures) < max_attempts:
            return None
        # every counted failure is inside the window, so the lock lifts as soon
        # as the oldest of them ages out - never later, never permanently
        return failures[-1].create_date + window

    @api.model
    def _record_attempt(self, login, ip, result):
        """Write one attempt row.

        Created with ``sudo`` because the authentication layer writes this, not
        the person trying to log in - there is no authenticated user yet, and no
        access-rights decision is being bypassed. Nobody is granted create
        rights on the model itself.
        """
        if not self._lockout_config()['enabled']:
            # switching the policy off makes the module inert: no lockouts and
            # no new rows either, rather than a log that silently keeps growing
            return self.browse()
        login = self._normalize_login(login)
        if not login:
            return self.browse()
        if result == 'blocked' and self._blocked_already_recorded(login):
            # One row per lockout, not one per knock. Somebody hammering a locked
            # login would otherwise write an unbounded number of rows between two
            # runs of the purge cron, which is a disk-fill vector on exactly the
            # workload this module exists to survive.
            return self.browse()
        record = self.sudo().create({
            'login': login,
            'ip': (ip or '')[:IP_MAX_LEN],
            'result': result,
        })
        self._flush_attempts()
        return record

    @api.model
    def _blocked_already_recorded(self, login):
        """Has this lockout already been written down once?"""
        config = self._lockout_config()
        since = fields.Datetime.now() - timedelta(minutes=config['lock_minutes'])
        return bool(self.sudo().search_count(
            [('login', '=', login), ('result', '=', 'blocked'),
             ('create_date', '>', since)]))

    @api.model
    def _notify_lockout(self, login, ip, locked_until):
        """Mail every Settings administrator that a lockout just started."""
        if not self._lockout_config()['alert']:
            return
        # Normalise first: this is called with the string straight off the login
        # form, so without it the payload below is unbounded in length and can
        # still carry the CR/LF that would let somebody forge mail headers.
        login = self._normalize_login(login)
        if not login:
            return
        # Only alert for logins that are real accounts on this database.
        # Lockouts still apply to invented logins - that is what stops the login
        # form being used to enumerate accounts - but mailing about them would
        # let an attacker turn N unauthenticated requests into N/5 messages to
        # every administrator. Nothing about this is visible to the attacker.
        if not self.env['res.users'].sudo().search_count(
                [('login', '=', login), ('active', '=', True)]):
            _logger.info(
                'auth_login_lockout: %r locked out but matches no active user, '
                'no alert sent', login)
            return
        group = self.env.ref('base.group_system', raise_if_not_found=False)
        if not group:
            return
        # read the membership relation directly: the model-level field was
        # renamed between series (res.users.groups_id became group_ids in 19.0)
        # while this relation table has been stable throughout
        self.env.cr.execute("""
            SELECT DISTINCT p.email
              FROM res_groups_users_rel rel
              JOIN res_users u ON u.id = rel.uid
              JOIN res_partner p ON p.id = u.partner_id
             WHERE rel.gid = %s
               AND u.active
               AND p.email IS NOT NULL
               AND p.email <> ''
        """, (group.id,))
        emails = sorted({row[0] for row in self.env.cr.fetchall()})
        if not emails:
            return
        # Everything below is attacker-controlled: the login is whatever was typed
        # into an unauthenticated login form. Escaping it is what stops somebody
        # from posting a login of "<img src=x onerror=...>" and having it rendered
        # inside the administrator's mail client.
        safe = {
            'login': escape(login),
            'ip': escape(ip or _('unknown')),
            'until': escape(fields.Datetime.to_string(locked_until)),
        }
        body = _(
            '<p>The login <strong>%(login)s</strong> has been locked out after '
            'repeated failed password attempts.</p>'
            '<ul><li>Last attempt from IP: %(ip)s</li>'
            '<li>Locked until (UTC): %(until)s</li></ul>'
            '<p>The lockout expires on its own. To let the account back in '
            'immediately, open Settings / Users and Companies / Login Attempts, '
            'select the failed attempts for this login and use the '
            '"Release lockout" action.</p>'
        ) % safe
        self.env['mail.mail'].sudo().create({
            # the subject is plain text, so it takes the raw login
            'subject': _('Security alert: login "%s" locked out') % login,
            'body_html': body,
            'email_to': ','.join(emails),
            'auto_delete': True,
        })

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def action_release_lockout(self):
        """Stop the selected failures from counting towards a lockout.

        The rows are kept - releasing must not erase the audit trail, it only
        takes the failures out of the running count. No ``sudo`` anywhere: the
        write below is what enforces that only Settings administrators may do
        this.
        """
        releasable = self.filtered(lambda a: a.result == 'failed' and not a.released)
        if releasable:
            releasable.write({'released': True})
        return True

    # ------------------------------------------------------------------
    # scheduled cleanup
    # ------------------------------------------------------------------
    @api.model
    def _gc_login_attempts(self):
        """Purge attempts older than the retention period."""
        config = self._lockout_config()
        cutoff = fields.Datetime.now() - timedelta(days=config['retention_days'])
        # Drain in batches rather than deleting a single capped slice. A brute
        # force writes rows far faster than one capped delete could remove them,
        # and a purge that never catches up is the same as having no retention
        # at all - the table would grow until the disk did.
        total = 0
        for _batch in range(GC_MAX_BATCHES):
            stale = self.sudo().search(
                [('create_date', '<', cutoff)], order='create_date asc', limit=GC_BATCH)
            if not stale:
                break
            total += len(stale)
            stale.unlink()
            if len(stale) < GC_BATCH:
                break
        if total:
            _logger.info('auth_login_lockout: purged %s login attempts older than %s',
                         total, fields.Datetime.to_string(cutoff))
        if total >= GC_BATCH * GC_MAX_BATCHES:
            _logger.warning(
                'auth_login_lockout: hit the %s row purge ceiling in one run; the '
                'attempt log is growing faster than it is being drained, which '
                'usually means a brute force is in progress - rate-limit at the '
                'reverse proxy', GC_BATCH * GC_MAX_BATCHES)
        return total
