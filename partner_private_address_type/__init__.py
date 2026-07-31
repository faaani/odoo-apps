# -*- coding: utf-8 -*-
# Part of partner_private_address_type. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from . import models

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Databases upgraded from Odoo 16 can still carry type='private' rows.

    Re-enabling the selection value would instantly hide such a partner from
    everyone outside the new group - including the linked user themselves,
    which is exactly what the module's constraints forbid. Reset those
    user-linked rows to 'other' (the constraints only fire on writes, so they
    cannot catch pre-existing data). Archived users are included: leaving
    their partner private would make any later unarchiving trip the
    constraint.
    """
    users = env['res.users'].sudo().with_context(active_test=False).search(
        [('partner_id.type', '=', 'private')])
    partners = users.partner_id
    if partners:
        partners.sudo().write({'type': 'other'})
        _logger.info(
            "partner_private_address_type: reset %d user-linked private "
            "partner(s) to 'other': %s", len(partners), partners.mapped('display_name'))


def uninstall_hook(env):
    """The 'private' selection value is removed together with this module.

    Move every partner still using it to 'other' so no row is left holding a
    value that no longer exists in the field selection. (Field-level safety
    net: the selection_add ondelete policy would fall back to 'contact' for
    any row this hook could not reach.)
    """
    env['res.partner'].with_context(active_test=False).sudo().search(
        [('type', '=', 'private')]
    ).write({'type': 'other'})
