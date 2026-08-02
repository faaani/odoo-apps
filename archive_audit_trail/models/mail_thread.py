# -*- coding: utf-8 -*-
# Part of archive_audit_trail. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import _, models
from odoo.tools import str2bool

_logger = logging.getLogger(__name__)

PARAM_ENABLED = 'archive_audit_trail.enabled'


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _archive_audit_enabled(self):
        try:
            return str2bool(self.env['ir.config_parameter'].sudo().get_param(
                PARAM_ENABLED, 'True'))
        except ValueError:
            return True

    def write(self, vals):
        # capture the previous state before the write so only real transitions
        # are logged (re-writing active=False on an archived record is a no-op)
        track = 'active' in vals and self._archive_audit_enabled()
        changed = self.browse()
        if track:
            new_state = bool(vals.get('active'))
            try:
                changed = self.filtered(lambda r: bool(r.active) != new_state)
            except Exception:  # noqa: BLE001 — never block a write over logging
                _logger.exception('archive_audit_trail: could not read active state.')
                track = False
        res = super(MailThread, self).write(vals)
        if track and changed:
            body = (_('Record restored from the archive.') if vals.get('active')
                    else _('Record archived.'))
            for record in changed:
                try:
                    # savepoint: a DB-level failure inside message_post (e.g. a
                    # mail_followers unique-constraint race) would otherwise
                    # abort the whole transaction and take the archive write
                    # down with it at commit — the try/except alone cannot
                    # un-poison the cursor.
                    with self.env.cr.savepoint():
                        record.message_post(body=body)
                except Exception as err:  # noqa: BLE001 — logging must never break archiving
                    _logger.warning(
                        'archive_audit_trail: could not log archive change on %s,%s: %s',
                        record._name, record.id, err)
        return res
