# -*- coding: utf-8 -*-
# Part of mail_outgoing_auto_bcc. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import SUPERUSER_ID, api

from . import models


def uninstall_hook(cr, registry):
    """Drop every configuration parameter this module created."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['ir.config_parameter'].search(
        [('key', '=like', 'mail_outgoing_auto_bcc.%')]).unlink()
