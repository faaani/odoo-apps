# -*- coding: utf-8 -*-
# Part of ir_logging_viewer. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..models.ir_logging import DEFAULT_RETENTION_DAYS, MIN_RETENTION_DAYS


class IrLoggingClearWizard(models.TransientModel):
    _name = 'ir.logging.clear.wizard'
    _description = 'Clear Server Log Entries'

    mode = fields.Selection(
        selection=[
            ('older', 'Delete entries older than a number of days'),
            ('all', 'Delete every log entry'),
        ],
        string='What To Delete', default='older', required=True,
        help='Either trim the table down to a recent window, or empty it completely.')
    days = fields.Integer(
        string='Days To Keep', default=DEFAULT_RETENTION_DAYS,
        help='Entries created more than this many days ago are deleted. '
             'Anything newer is kept.')
    total_count = fields.Integer(
        string='Entries Stored', compute='_compute_counts',
        help='Total number of log entries currently in the database.')
    match_count = fields.Integer(
        string='Entries To Delete', compute='_compute_counts',
        help='How many entries the current choice would delete.')
    confirm = fields.Boolean(
        string='Yes, delete them permanently',
        help='Deleting log entries cannot be undone. The action refuses to run '
             'until this box is ticked.')

    @api.depends('mode', 'days')
    def _compute_counts(self):
        logs = self.env['ir.logging']
        # One aggregate query for the whole set, never a browse of the table.
        total = logs._logging_viewer_count()
        for wizard in self:
            wizard.total_count = total
            if wizard.mode == 'all':
                wizard.match_count = total
            elif wizard.days and wizard.days >= MIN_RETENTION_DAYS:
                cutoff = fields.Datetime.now() - timedelta(days=wizard.days)
                wizard.match_count = logs._logging_viewer_count(cutoff=cutoff)
            else:
                wizard.match_count = 0

    def action_clear(self):
        """Delete the selected log entries once the confirmation is ticked."""
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_(
                'Only a Settings administrator may delete server log entries.'))
        if not self.confirm:
            raise UserError(_(
                'Tick the confirmation box first: deleted log entries cannot '
                'be recovered.'))
        logs = self.env['ir.logging']
        if self.mode == 'all':
            removed = logs._logging_viewer_delete()
        else:
            if self.days < MIN_RETENTION_DAYS:
                raise UserError(_(
                    'Keep at least one day of log entries, or choose '
                    '"Delete every log entry".'))
            removed = logs._logging_viewer_delete_older_than(self.days)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Server log entries deleted'),
                'message': _('%s log entries were deleted.') % removed,
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
