# -*- coding: utf-8 -*-
# Part of database_neutralize_toggle. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import json
import logging

from . import models
from .models.res_config_settings import (
    NEUTRALIZE_MODELS,
    PARAM_ACTIVE,
    PARAM_SNAPSHOT,
)

_logger = logging.getLogger(__name__)


def _restore_snapshot(env):
    """Put the snapshotted 'active' flags back and drop both config params.

    Standalone on purpose: at uninstall time the module's own field and view
    inheritance are already gone, so only base models are touched here.
    """
    icp = env['ir.config_parameter'].sudo()
    try:
        snapshot = json.loads(icp.get_param(PARAM_SNAPSHOT) or '[]')
    except ValueError:
        snapshot = []
    for entry in snapshot:
        try:
            model, record_id, was_active = entry
        except (TypeError, ValueError):
            continue
        if model not in NEUTRALIZE_MODELS or model not in env:
            continue
        record = env[model].with_context(
            active_test=False).browse(record_id).exists()
        if record and bool(record.active) != bool(was_active):
            record.write({'active': bool(was_active)})
    icp.set_param(PARAM_SNAPSHOT, False)
    icp.set_param(PARAM_ACTIVE, False)


def uninstall_hook(*args):
    """Uninstalling while Sandbox Mode is active must not strand the database
    neutralized: restore the saved state and remove both config parameters.

    Odoo 17.0+ calls hooks with (env,); earlier series with (cr, registry).
    """
    try:
        if len(args) == 1:
            env = args[0]
        else:
            from odoo import SUPERUSER_ID, api
            env = api.Environment(args[0], SUPERUSER_ID, {})
        _restore_snapshot(env)
    except Exception:  # noqa: BLE001 - never let cleanup break an uninstall
        _logger.warning(
            'database_neutralize_toggle: could not restore the neutralize '
            'snapshot on uninstall', exc_info=True)
