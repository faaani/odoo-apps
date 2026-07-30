# -*- coding: utf-8 -*-
# Part of attachment_upload_guard. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import base64
import os

from odoo import _, api, models, SUPERUSER_ID
from odoo.exceptions import UserError
from odoo.tools import str2bool

PARAM_ENABLED = 'attachment_upload_guard.enabled'
PARAM_BLOCKED_EXT = 'attachment_upload_guard.blocked_extensions'
PARAM_MAX_MB = 'attachment_upload_guard.max_size_mb'
DEFAULT_BLOCKED = 'exe,bat,cmd,com,scr,pif,msi,jar,vbs,ps1,sh,dll'
DEFAULT_MAX_MB = 25
# ir.config_parameter.get_param() returns the DEFAULT for any falsy stored
# value, so "block nothing" cannot be stored as an empty string — it is kept
# as this sentinel instead.
NO_BLOCKED_SENTINEL = 'none'
# Attachments Odoo itself creates: web assets, view/report artefacts, module
# data. Blocking these would break the UI, so they are always allowed.
SYSTEM_MODELS = ('ir.ui.view', 'ir.asset', 'ir.actions.report', 'ir.module.module')


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def _upload_guard_config(self):
        icp = self.env['ir.config_parameter'].sudo()
        try:
            enabled = str2bool(icp.get_param(PARAM_ENABLED, 'True'))
        except ValueError:
            enabled = True
        try:
            max_mb = int(icp.get_param(PARAM_MAX_MB, DEFAULT_MAX_MB))
        except (TypeError, ValueError):
            max_mb = DEFAULT_MAX_MB
        raw = icp.get_param(PARAM_BLOCKED_EXT, DEFAULT_BLOCKED) or ''
        if raw.strip().lower() == NO_BLOCKED_SENTINEL:
            raw = ''
        blocked = {e.strip().lower().lstrip('.') for e in raw.split(',') if e.strip()}
        return {'enabled': enabled, 'max_mb': max(max_mb, 0), 'blocked': blocked}

    @api.model
    def _upload_guard_size_of(self, vals):
        datas = vals.get('datas') or vals.get('raw')
        if not datas:
            return 0
        if isinstance(datas, bytes) and not vals.get('datas'):
            return len(datas)
        try:
            return len(base64.b64decode(datas))
        except Exception:  # noqa: BLE001 — unparsable payload is core's problem, not ours
            return 0

    @api.model
    def _upload_guard_check(self, vals):
        # env.su alone is NOT an exemption: the chatter/Discuss upload route
        # creates attachments with sudo() while env.uid stays the real user,
        # and that is exactly the path this policy must cover.
        if self.env.uid == SUPERUSER_ID:
            return  # module install, crons, mail gateway: genuine system work
        if self.env.su and vals.get('res_model') in SYSTEM_MODELS:
            return  # web assets / report artefacts, which must never be blocked
        if self.env.context.get('upload_guard_skip'):
            return
        config = self._upload_guard_config()
        if not config['enabled']:
            return
        name = vals.get('name') or ''
        ext = os.path.splitext(name)[1].lower().lstrip('.')
        if ext and ext in config['blocked']:
            raise UserError(_(
                'Files of type ".%(ext)s" cannot be attached here. '
                'Blocked file types: %(list)s.'
            ) % {'ext': ext, 'list': ', '.join(sorted(config['blocked']))})
        if config['max_mb']:
            size = self._upload_guard_size_of(vals)
            limit = config['max_mb'] * 1024 * 1024
            if size > limit:
                raise UserError(_(
                    'The file "%(name)s" is %(size).1f MB, which is larger than '
                    'the %(max)s MB limit for attachments.'
                ) % {'name': name or _('unnamed'),
                     'size': size / (1024.0 * 1024.0), 'max': config['max_mb']})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._upload_guard_check(vals)
        return super(IrAttachment, self).create(vals_list)

    def write(self, vals):
        # renaming a clean file to .exe, or swapping its payload for an
        # oversized one, must not slip past a create-only guard
        if 'name' in vals or 'datas' in vals or 'raw' in vals:
            for record in self:
                merged = {
                    'name': vals.get('name', record.name),
                    'res_model': vals.get('res_model', record.res_model),
                }
                if 'datas' in vals or 'raw' in vals:
                    merged['datas'] = vals.get('datas')
                    merged['raw'] = vals.get('raw')
                    self._upload_guard_check(merged)
                else:
                    # size unchanged: only re-check the name policy
                    self._upload_guard_check(merged)
        return super(IrAttachment, self).write(vals)
