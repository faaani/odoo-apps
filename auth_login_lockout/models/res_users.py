# -*- coding: utf-8 -*-
# Part of auth_login_lockout. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import api, models, registry, SUPERUSER_ID
from odoo.exceptions import AccessDenied
from odoo.http import request

_logger = logging.getLogger(__name__)


def _remote_ip():
    """Source address of the current request, or '' outside a request.

    ``_login`` is also reached from XML-RPC, the shell and tests, where there is
    no request at all - hence the guard.
    """
    try:
        if request:
            return request.httprequest.environ.get('REMOTE_ADDR') or ''
    except Exception:  # pragma: no cover - never let telemetry break a login
        pass
    return ''


class Users(models.Model):
    _inherit = 'res.users'

    # ------------------------------------------------------------------
    # every helper runs in its own cursor:
    #  * at this point the login has no transaction of its own yet, and
    #  * a failed login rolls back, which would take the evidence with it.
    #
    # The commits below are therefore on a cursor this module opened itself,
    # never on a caller's transaction - the same thing res.users._login and
    # auth_ldap do in core. Without them a brute-force attempt would roll back
    # its own record and the counter would never rise, so `invalid-commit` is
    # disabled deliberately and only on those two lines.
    # ------------------------------------------------------------------
    @classmethod
    def _lockout_guard(cls, db, login, ip):
        """Return the lockout expiry if this login is currently locked out."""
        with registry(db).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            attempts = env['auth.login.attempt']
            locked_until = attempts._locked_until(login)
            if locked_until:
                try:
                    # record the rejection as 'blocked', not as another failure:
                    # counting it would let an attacker keep a colleague locked
                    # out for as long as they keep knocking
                    attempts._record_attempt(login, ip, 'blocked')
                    cr.commit()  # pylint: disable=invalid-commit
                except Exception:
                    # the decision has already been taken and it stands: failing
                    # to write the audit row must never let the attempt through
                    cr.rollback()
                    _logger.exception(
                        'auth_login_lockout: could not record a blocked attempt')
            return locked_until

    @classmethod
    def _lockout_record(cls, db, login, ip, result):
        """Record one finished attempt and raise the alert when a lock starts."""
        with registry(db).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            attempts = env['auth.login.attempt']
            attempts._record_attempt(login, ip, result)
            if result == 'failed':
                # this code path is only reached when the login was not locked
                # beforehand, so a lock existing now means this very failure is
                # the one that crossed the threshold - the alert fires once
                locked_until = attempts._locked_until(login)
                if locked_until:
                    _logger.warning(
                        'auth_login_lockout: login %r locked out until %s UTC after '
                        'repeated failures (last attempt from %s)',
                        login, locked_until, ip or 'unknown')
                    attempts._notify_lockout(login, ip, locked_until)
            cr.commit()  # pylint: disable=invalid-commit

    @classmethod
    def _login(cls, db, login, password, user_agent_env):
        ip = _remote_ip()
        try:
            locked_until = cls._lockout_guard(db, login, ip)
        except Exception:
            # a bug in the throttling must never make the database
            # unloggable-into: fall through to standard authentication
            _logger.exception(
                'auth_login_lockout: lockout check failed, allowing the attempt through')
            locked_until = None

        if locked_until:
            _logger.info('auth_login_lockout: refused login for %r from %s, locked until %s UTC',
                         login, ip or 'unknown', locked_until)
            # deliberately the plain "access denied" the caller would get from a
            # wrong password: telling them a lockout is running, or how long it
            # lasts, would hand an attacker the policy for free
            raise AccessDenied()

        try:
            uid = super(Users, cls)._login(db, login, password, user_agent_env=user_agent_env)
        except AccessDenied:
            try:
                cls._lockout_record(db, login, ip, 'failed')
            except Exception:
                _logger.exception('auth_login_lockout: could not record a failed login')
            raise

        try:
            cls._lockout_record(db, login, ip, 'success')
        except Exception:
            _logger.exception('auth_login_lockout: could not record a successful login')
        return uid
