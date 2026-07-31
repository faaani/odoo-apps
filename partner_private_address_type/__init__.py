# -*- coding: utf-8 -*-
# Part of partner_private_address_type. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from . import models

_logger = logging.getLogger(__name__)


def uninstall_hook(cr, registry):
    """Revoke the core-group access this module granted.

    Membership of the hidden core group base.group_private_addresses is
    materialized on users, so it would survive the deletion of this module's
    group. Strip it from users who only held it through this module's group -
    never from administrators (base.group_system) or from users who hold it
    through another implying group (e.g. an HR access level) - so uninstall
    restores exactly the access posture the module found at install time.
    """
    try:
        from odoo import SUPERUSER_ID, api

        env = api.Environment(cr, SUPERUSER_ID, {})
        module_group = env.ref(
            'partner_private_address_type.group_private_address',
            raise_if_not_found=False)
        core_group = env.ref('base.group_private_addresses',
                             raise_if_not_found=False)
        if not module_group or not core_group:
            return
        Groups = env['res.groups'].sudo()
        # groups that will still grant the core group once this module is
        # gone: transitive impliers of the core group, this module's excluded
        keep_groups = Groups.browse()
        frontier = Groups.search([('implied_ids', 'in', core_group.id),
                                  ('id', '!=', module_group.id)])
        while frontier:
            keep_groups |= frontier
            frontier = Groups.search([
                ('implied_ids', 'in', frontier.ids),
                ('id', 'not in', (keep_groups | module_group).ids)])
        keep_users = keep_groups.mapped('users') \
            | env.ref('base.group_system').sudo().users
        strip = module_group.users - keep_users
        if strip:
            core_group.sudo().write({'users': [(3, user.id) for user in strip]})
            _logger.info(
                "partner_private_address_type: revoked core private-address "
                "access from %s", strip.mapped('login'))
        if hasattr(env, 'flush_all'):
            env.flush_all()
        else:
            env['base'].flush()
    except Exception:  # noqa: BLE001 - cleanup must never break uninstall
        _logger.exception(
            "partner_private_address_type: could not clean up core "
            "private-address group membership")
