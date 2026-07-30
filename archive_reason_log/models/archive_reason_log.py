# -*- coding: utf-8 -*-
# Part of archive_reason_log. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ArchiveReasonLog(models.Model):
    _name = 'archive.reason.log'
    _description = 'Archive Log'
    _order = 'archive_date desc, id desc'
    _rec_name = 'record_name'

    # 'set null', never 'cascade': uninstalling the module that owned an
    # archived model must not delete the history of what was archived. res_model
    # below keeps the technical name whatever happens to the ir.model row.
    model_id = fields.Many2one(
        'ir.model', string='Model', ondelete='set null', index=True)
    res_model = fields.Char(string='Model Name', required=True, index=True)
    res_id = fields.Integer(string='Record ID', required=True, index=True)
    record_name = fields.Char(string='Record', required=True)
    reason_id = fields.Many2one(
        'archive.reason', string='Reason', required=True, ondelete='restrict',
        index=True)
    note = fields.Text(string='Explanation')
    user_id = fields.Many2one(
        'res.users', string='Archived by', required=True, index=True,
        default=lambda self: self.env.user, ondelete='restrict')
    archive_date = fields.Datetime(
        string='Archived on', required=True, index=True,
        default=fields.Datetime.now)
    state = fields.Selection(
        [('archived', 'Archived'), ('restored', 'Restored')],
        string='Status', required=True, default='archived', index=True)
    restore_date = fields.Datetime(string='Restored on', readonly=True)
    restore_user_id = fields.Many2one(
        'res.users', string='Restored by', readonly=True, ondelete='restrict')

    def action_open_record(self):
        """Open the archived record itself (normal access rights apply)."""
        self.ensure_one()
        if self.res_model not in self.env:
            raise UserError(
                _('The model "%s" is not installed any more.') % self.res_model)
        record = self.env[self.res_model].with_context(
            active_test=False).browse(self.res_id).exists()
        if not record:
            raise UserError(_('That record has been deleted since it was archived.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'active_test': False},
        }

    @api.model
    def _mark_restored(self, records):
        """Close the open log entries of ``records`` when they are unarchived.

        sudo() is deliberate and narrow: this is an audit table, so ordinary
        users hold no write right on it (see ir.model.access.csv). The record
        they just restored may well have been archived by somebody else, and the
        history row must still be closed. Nothing is created or deleted here.
        """
        if not records:
            return
        logs = self.sudo().search([
            ('res_model', '=', records._name),
            ('res_id', 'in', records.ids),
            ('state', '=', 'archived'),
        ])
        if logs:
            logs.write({
                'state': 'restored',
                'restore_date': fields.Datetime.now(),
                'restore_user_id': self.env.uid,
            })
