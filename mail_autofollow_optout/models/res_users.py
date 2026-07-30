# -*- coding: utf-8 -*-
# Part of mail_autofollow_optout. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

FIELD = 'no_auto_follow'


class ResUsers(models.Model):
    _inherit = 'res.users'

    no_auto_follow = fields.Boolean(
        string='Do Not Follow Records Automatically',
        default=False,
        help='When enabled, you are no longer subscribed automatically to '
             'records you create, comment on or get assigned. You can still '
             'follow anything manually with the Follow button.',
    )

    def _register_hook(self):
        """Let users toggle their own preference.

        14.0/15.0 keep SELF_*_FIELDS as plain class lists while 16.0+ expose
        them as properties; assigning a plain list on the registry class
        shadows either shape safely.
        """
        res = super(ResUsers, self)._register_hook()
        users = self.env['res.users']
        cls = type(users)
        for attr in ('SELF_READABLE_FIELDS', 'SELF_WRITEABLE_FIELDS'):
            current = list(getattr(users, attr, []) or [])
            if FIELD not in current:
                setattr(cls, attr, current + [FIELD])
        return res
