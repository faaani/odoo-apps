# -*- coding: utf-8 -*-
# Part of password_expiry_policy. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

import werkzeug.utils

from odoo import _, http
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request
from odoo.service import security

_logger = logging.getLogger(__name__)


class PasswordExpiryController(http.Controller):

    @http.route('/password_expiry/change', type='http', auth='user',
                methods=['GET', 'POST'])
    def password_expiry_change(self, **post):
        """Change-password page an expired user is sent to.

        Always reachable, also when the policy is off or the password is still
        fresh, so the redirect can never end in a loop.
        """
        user = request.env.user
        values = {
            'expired': user._password_is_expired(),
            'user_login': user.login,
            'error': None,
            'disable_database_manager': True,
        }
        if request.httprequest.method == 'POST':
            old_password = post.get('old_password') or ''
            new_password = post.get('new_password') or ''
            confirm_password = post.get('confirm_password') or ''
            if not new_password or new_password != confirm_password:
                values['error'] = _('The two new passwords do not match.')
            elif new_password == old_password:
                values['error'] = _('The new password must be different from the current one.')
            else:
                try:
                    request.env['res.users'].change_password(old_password, new_password)
                except AccessDenied:
                    values['error'] = _('The current password is not correct.')
                except UserError as exc:
                    values['error'] = exc.args[0] if exc.args else _('The password could not be changed.')
                else:
                    # The session token is derived from the password hash, so a
                    # change invalidates the running session: refresh it or the
                    # user is bounced straight back to the login screen.
                    request.session.session_token = security.compute_session_token(
                        request.session, request.env)
                    _logger.info('Password expiry: %r set a new password.', user.login)
                    return werkzeug.utils.redirect('/', 303)
        return request.render('password_expiry_policy.change_password_page', values)
