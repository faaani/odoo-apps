# -*- coding: utf-8 -*-
# Part of mail_outgoing_auto_bcc. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from . import models


def uninstall_hook(env):
    """Drop every configuration parameter this module created."""
    env['ir.config_parameter'].sudo().search(
        [('key', '=like', 'mail_outgoing_auto_bcc.%')]).unlink()
