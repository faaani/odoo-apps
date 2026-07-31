# -*- coding: utf-8 -*-
# Part of password_expiry_policy. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
from datetime import timedelta

from odoo import SUPERUSER_ID, api, fields, models

_logger = logging.getLogger(__name__)

PARAM_ENABLED = 'password_expiry_policy.enabled'
PARAM_DAYS = 'password_expiry_policy.days'

DEFAULT_DAYS = 90
# A typo such as "0" or "1" would expire every account on the next page load,
# so the period is clamped both when it is saved and when it is read.
MIN_DAYS = 7
MAX_DAYS = 3650


class ResUsers(models.Model):
    _inherit = 'res.users'

    password_write_date = fields.Datetime(
        string='Last Password Change',
        readonly=True,
        copy=False,
        default=fields.Datetime.now,
        help='When this user last changed their password. Existing users are '
             'stamped with the installation date, so installing this module '
             'never expires anybody retroactively.',
    )
    password_expiry_exempt = fields.Boolean(
        string='Exempt from Password Expiry',
        default=False,
        copy=False,
        help='This user is never asked to change their password, whatever the '
             'policy says. Use it for integration accounts and for a break-glass '
             'administrator.',
    )
    password_expiry_date = fields.Datetime(
        string='Password Expires On',
        compute='_compute_password_expiry_date',
        help='Date on which this user will be asked for a new password. Empty '
             'when the policy is off or the user is exempt.',
    )

    # ------------------------------------------------------------------
    # policy
    # ------------------------------------------------------------------
    @api.model
    def _password_expiry_config(self):
        """Return ``(enabled, days)`` for the password rotation policy."""
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param(PARAM_ENABLED, 'False') != 'True':
            return False, DEFAULT_DAYS
        raw = icp.get_param(PARAM_DAYS, DEFAULT_DAYS)
        try:
            days = int(raw)
        except (TypeError, ValueError):
            _logger.warning(
                'Invalid %s value %r, falling back on %s days.',
                PARAM_DAYS, raw, DEFAULT_DAYS)
            days = DEFAULT_DAYS
        return True, min(max(days, MIN_DAYS), MAX_DAYS)

    def _password_expiry_is_exempt(self):
        """Users the policy must never be able to lock out."""
        self.ensure_one()
        if not self.id or self.id == SUPERUSER_ID:
            return True
        admin = self.env.ref('base.user_admin', raise_if_not_found=False)
        if admin and self.id == admin.id:
            return True
        # Portal, public and any other share user: they have no backend to be
        # redirected to, and the change form is a backend page.
        if self.share or not self.has_group('base.group_user'):
            return True
        return bool(self.password_expiry_exempt)

    def _password_is_expired(self):
        """True when this user must change their password before continuing."""
        self.ensure_one()
        enabled, days = self._password_expiry_config()
        if not enabled:
            return False
        if self._password_expiry_is_exempt():
            return False
        if not self.password_write_date:
            # Unknown password age: fail open rather than lock the user out.
            return False
        return fields.Datetime.now() >= self.password_write_date + timedelta(days=days)

    @api.depends('password_write_date', 'password_expiry_exempt', 'share')
    def _compute_password_expiry_date(self):
        enabled, days = self._password_expiry_config()
        for user in self:
            expiry = False
            if enabled and user.password_write_date and not user._password_expiry_is_exempt():
                expiry = user.password_write_date + timedelta(days=days)
            user.password_expiry_date = expiry

    # ------------------------------------------------------------------
    # stamping
    # ------------------------------------------------------------------
    def _password_expiry_stamp(self):
        """Record that these users just changed their password.

        Written in SQL exactly like core's own ``_set_encrypted_password``: this
        runs from the ``password`` inverse and from ``write()``, where a nested
        ORM write would recurse, and where a plain user changing their own
        password has no write access to ``res.users``.
        """
        if not self.ids:
            return
        self.env.cr.execute(
            'UPDATE res_users SET password_write_date = %s WHERE id IN %s',
            (fields.Datetime.now(), tuple(self.ids)),
        )
        # invalidate_recordset() only exists from 16.0; 14.0/15.0 use invalidate_cache()
        if hasattr(self, 'invalidate_recordset'):
            self.invalidate_recordset(['password_write_date'])
        else:
            self.invalidate_cache(['password_write_date'], self.ids)

    def _set_password(self):
        # Inverse of the ``password`` field: reached by write({'password': ...}),
        # by the change-password wizards and by _change_password().
        # The pending value MUST be read before super(): core invalidates the
        # password cache, so reading it afterwards recomputes it to '' and fires
        # this very inverse again with an empty password.
        changed = self.filtered(lambda user: user.password)
        super(ResUsers, self)._set_password()
        changed._password_expiry_stamp()

    def write(self, vals):
        res = super(ResUsers, self).write(vals)
        # 'password' is inverted by super() through _set_password(), so this is
        # belt and braces. 'new_password' is deliberately NOT stamped here: core
        # assigns it to 'password' inside its own inverse, where the field is
        # protected, so no new hash is stored in that write. Stamping it would
        # reset the clock without the password having changed.
        if vals.get('password'):
            self._password_expiry_stamp()
        return res

    @api.model
    def change_password(self, old_passwd, new_passwd):
        res = super(ResUsers, self).change_password(old_passwd, new_passwd)
        self.env.user._password_expiry_stamp()
        return res
