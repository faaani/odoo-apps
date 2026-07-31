# -*- coding: utf-8 -*-
# Part of password_expiry_policy. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import werkzeug.exceptions
import werkzeug.utils

from odoo import SUPERUSER_ID, models
from odoo.http import request

PASSWORD_CHANGE_URL = '/password_expiry/change'

# Everything an expired user must still be able to reach, or the redirect turns
# into a loop: the change form itself, login/logout, the database manager and
# whatever the browser needs to render those pages.
EXEMPT_PREFIXES = (
    '/password_expiry/',
    '/web/login',
    '/web/logout',
    '/web/session/',
    '/web/signup',
    '/web/reset_password',
    '/web/assets',
    '/web/static/',
    '/web/binary/',
    '/web/image',
    '/web/webclient/',
    '/web/database/',
    '/web/health',
    '/websocket',
    '/longpolling/',
)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _authenticate(cls, endpoint):
        # 14.0/15.0 return the resolved auth method from here.
        res = super()._authenticate(endpoint)
        cls._password_expiry_guard()
        return res

    @classmethod
    def _password_expiry_guard(cls):
        """Redirect a user whose password expired to the change-password page.

        Deliberately narrow: it only fires on a GET that asks for HTML — in
        other words on a browser page load. XML-RPC, JSON-RPC,
        /web/session/authenticate, asset, image and download requests never
        reach the redirect, and database initialisation, cron jobs and the mail
        gateway never go through ir.http at all.

        The check is hung on the authentication hook rather than on
        ``_auth_method_user`` because the backend entry points (``/`` and
        ``/web``) are declared ``auth='none'`` and validate the session
        themselves, so ``_auth_method_user`` never runs for them.
        """
        httprequest = request.httprequest
        if httprequest.method != 'GET':
            return
        if 'text/html' not in (httprequest.headers.get('Accept') or ''):
            return
        if (httprequest.path or '/').startswith(EXEMPT_PREFIXES):
            return
        uid = request.session.uid
        if not uid:
            return
        # The endpoint may be auth='none', in which case request.env has no
        # user: read the policy from the session uid instead. Same shape as
        # core's own env.user, which is likewise evaluated as superuser.
        env = request.env(user=SUPERUSER_ID)
        if not env['res.users']._password_expiry_config()[0]:
            return  # policy off: one cheap parameter read and out
        user = env['res.users'].browse(uid).exists()
        if not user or not user._password_is_expired():
            return
        werkzeug.exceptions.abort(
            werkzeug.utils.redirect(PASSWORD_CHANGE_URL, 303))
