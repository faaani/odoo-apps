# -*- coding: utf-8 -*-
# Part of duplicate_attachment_cleaner. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .duplicate_attachment_scan import format_bytes


class DuplicateAttachmentClean(models.TransientModel):
    _name = 'duplicate.attachment.clean'
    _description = 'Duplicate Attachment Clean-up Confirmation'

    scan_id = fields.Many2one(
        'duplicate.attachment.scan', string='Scan', required=True, ondelete='cascade')
    scope = fields.Selection(related='scan_id.scope', string='Look For', readonly=True)
    group_count = fields.Integer(
        string='Groups Selected', compute='_compute_summary')
    delete_count = fields.Integer(
        string='Copies To Delete (estimate)', compute='_compute_summary')
    keep_count = fields.Integer(
        string='Copies Kept', compute='_compute_summary')
    freed_display = fields.Char(
        string='Redundant Space (estimate)', compute='_compute_summary')
    confirm = fields.Boolean(
        string='I understand the extra copies will be deleted permanently')

    @api.depends('scan_id.line_ids.selected', 'scan_id.line_ids.copy_count')
    def _compute_summary(self):
        for wizard in self:
            lines = wizard.scan_id.line_ids.filtered('selected')
            wizard.group_count = len(lines)
            wizard.delete_count = sum(max(0, line.copy_count - 1) for line in lines)
            wizard.keep_count = len(lines)
            wizard.freed_display = format_bytes(sum(lines.mapped('wasted_bytes')))

    def action_confirm(self):
        self.ensure_one()
        if not self.confirm:
            raise UserError(_(
                'Tick the confirmation box to delete the extra copies. '
                'Nothing has been deleted.'))
        self.scan_id._perform_cleanup()
        return self.scan_id.action_view_result()
