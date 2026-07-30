# -*- coding: utf-8 -*-
# Part of archive_reason_log. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ArchiveReason(models.Model):
    _name = 'archive.reason'
    _description = 'Archive Reason'
    _order = 'sequence, name'

    name = fields.Char(
        string='Reason', required=True,
        help='Shown in the "Archive with Reason" dialog and in the archive log.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(
        default=True,
        help='Archived reasons are no longer proposed, but the log entries that '
             'already use them are kept intact.')
    note_mode = fields.Selection(
        [('optional', 'Optional'),
         ('required', 'Required'),
         ('forbidden', 'Not allowed')],
        string='Free-text Explanation', default='optional', required=True,
        help='Optional: the person archiving may add an explanation.\n'
             'Required: archiving is refused until an explanation is typed.\n'
             'Not allowed: the explanation box is hidden and any text is refused.')
    model_ids = fields.Many2many(
        'ir.model', 'archive_reason_ir_model_rel', 'reason_id', 'model_id',
        string='Limit to Models', domain=[('transient', '=', False)],
        help='Leave empty to offer this reason on every model.')
    description = fields.Char(
        string='Guidance',
        help='Optional hint shown to the user, e.g. "quote the duplicate record".')
    log_count = fields.Integer(string='Archives', compute='_compute_log_count')

    @api.constrains('name')
    def _check_unique_name(self):
        # A case-insensitive unique index would need raw DDL to stay portable
        # across the supported series, and this table is a short configuration
        # list, so the check lives here: one aggregate query per record.
        for reason in self:
            name = (reason.name or '').strip()
            if not name:
                continue
            # '=ilike' feeds the value straight to SQL ILIKE, so % and _ inside
            # a reason name ("50% off") would otherwise behave as wildcards.
            pattern = (name.replace('\\', '\\\\')
                       .replace('%', '\\%').replace('_', '\\_'))
            duplicate = self.with_context(active_test=False).search_count([
                ('name', '=ilike', pattern), ('id', '!=', reason.id)])
            if duplicate:
                raise ValidationError(
                    _('An archive reason named "%s" already exists.') % name)

    def _compute_log_count(self):
        # search_count is a single aggregate query per reason; the reason list is
        # a handful of configuration rows, never a table scan. sudo() so the
        # count is the real one: this field is only shown to Settings
        # administrators, whose own record rule would otherwise hide the entries
        # created by other users.
        Log = self.env['archive.reason.log'].sudo()
        for reason in self:
            reason.log_count = (
                Log.search_count([('reason_id', '=', reason.id)]) if reason.id else 0)

    def action_view_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Archive Log'),
            'res_model': 'archive.reason.log',
            'view_mode': 'list,form',
            'domain': [('reason_id', '=', self.id)],
        }
