# -*- coding: utf-8 -*-
# Part of database_neutralize_toggle. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import json

from odoo import _, fields, models
from odoo.exceptions import AccessError

PARAM_ACTIVE = 'database_neutralize_toggle.active'
PARAM_SNAPSHOT = 'database_neutralize_toggle.snapshot'
# Models whose 'active' flag is snapshotted and cleared while sandboxed.
# fetchmail.server is optional: it only exists once incoming mail is installed.
NEUTRALIZE_MODELS = ('ir.mail_server', 'fetchmail.server', 'ir.cron')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Explicit get_values/set_values on purpose: config_parameter= cannot
    # round-trip falsy values, and toggling has side effects beyond a param.
    sandbox_mode = fields.Boolean(
        string='Sandbox Mode',
        help='Snapshot and deactivate every outgoing mail server, incoming '
             'mail server and scheduled action, and show a warning banner. '
             'Switching it back off restores the exact previous state.')

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res['sandbox_mode'] = self._sandbox_is_active()
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        currently_active = self._sandbox_is_active()
        if self.sandbox_mode and not currently_active:
            self._sandbox_neutralize()
        elif not self.sandbox_mode and currently_active:
            self._sandbox_restore()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _sandbox_is_active(self):
        return self.env['ir.config_parameter'].sudo().get_param(PARAM_ACTIVE) == '1'

    def _sandbox_check_access(self):
        # The settings page is already admin-only; this guard covers direct
        # RPC calls to the helpers.
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(
                _('Only administrators (Settings access) may toggle Sandbox Mode.'))

    def _sandbox_neutralize(self):
        """Snapshot then deactivate mail servers, fetchmail servers and crons."""
        self._sandbox_check_access()
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param(PARAM_ACTIVE) == '1' and icp.get_param(PARAM_SNAPSHOT):
            # Already neutralized: never overwrite the pre-sandbox snapshot
            # with the already-neutralized state.
            return
        snapshot = []
        for model in NEUTRALIZE_MODELS:
            if model not in self.env:
                continue
            records = self.env[model].with_context(active_test=False).search([])
            snapshot.extend([model, record.id, bool(record.active)]
                            for record in records)
            records.filtered('active').write({'active': False})
        icp.set_param(PARAM_SNAPSHOT, json.dumps(snapshot))
        icp.set_param(PARAM_ACTIVE, '1')

    def _sandbox_restore(self):
        """Put the snapshotted 'active' flags back, then drop the snapshot.

        Records deleted while sandboxed are skipped silently; records created
        while sandboxed are left exactly as they are.
        """
        self._sandbox_check_access()
        icp = self.env['ir.config_parameter'].sudo()
        try:
            snapshot = json.loads(icp.get_param(PARAM_SNAPSHOT) or '[]')
        except ValueError:
            snapshot = []
        for entry in snapshot:
            try:
                model, record_id, was_active = entry
            except (TypeError, ValueError):
                continue
            if model not in NEUTRALIZE_MODELS or model not in self.env:
                continue
            record = self.env[model].with_context(
                active_test=False).browse(record_id).exists()
            if record and bool(record.active) != bool(was_active):
                record.write({'active': bool(was_active)})
        icp.set_param(PARAM_SNAPSHOT, False)
        icp.set_param(PARAM_ACTIVE, '0')
