# -*- coding: utf-8 -*-
# Part of default_value_manager. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Entries listed one by one in the confirmation screen before it says "and N more".
PREVIEW_LIMIT = 20


class DefaultValueDeleteWizard(models.TransientModel):
    _name = 'default.value.delete.wizard'
    _description = 'Delete Default Values'

    entry_count = fields.Integer(string='Selected Defaults', readonly=True)
    preview = fields.Text(
        string='About To Be Deleted', readonly=True,
        help='The default values that will be removed, with their scope and '
             'their current value.',
    )

    @api.model
    def _selected_entries(self):
        """The entries the wizard was opened on, read with the user's rights."""
        if self.env.context.get('active_model') not in (False, None, 'default.value.entry'):
            raise UserError(_('This screen only deletes default values.'))
        entry_ids = self.env.context.get('active_ids') or []
        if not entry_ids and self.env.context.get('active_id'):
            entry_ids = [self.env.context['active_id']]
        return self.env['default.value.entry'].browse(entry_ids).exists()

    @api.model
    def default_get(self, fields_list):
        result = super(DefaultValueDeleteWizard, self).default_get(fields_list)
        entries = self._selected_entries()
        lines = []
        for entry in entries[:PREVIEW_LIMIT]:
            scope = []
            scope.append(entry.user_id.display_name if entry.user_id else _('all users'))
            scope.append(entry.company_id.display_name if entry.company_id else _('all companies'))
            lines.append('%s = %s  (%s)' % (
                entry.complete_name, entry.value_display or '', ', '.join(scope)))
        if len(entries) > PREVIEW_LIMIT:
            lines.append(_('... and %s more', len(entries) - PREVIEW_LIMIT))
        result.update(entry_count=len(entries), preview='\n'.join(lines))
        return result

    def action_delete(self):
        self.ensure_one()
        entries = self._selected_entries()
        if not entries:
            raise UserError(_('The selected default values no longer exist.'))
        # the entry model enforces the group and ir.default enforces the access
        # rights and record rules of the current user
        entries.action_delete_defaults()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Default values deleted'),
                'message': _('%s default value(s) removed. Nothing else was changed.',
                             len(entries)),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
