# -*- coding: utf-8 -*-
# Part of menu_access_visibility. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..models.ir_ui_menu import clear_menu_caches, menu_groups_field

_logger = logging.getLogger(__name__)

MODE_SELECTION = [
    ('add', 'Give these groups access to the selected items'),
    ('remove', 'Take these groups off the selected items'),
]


class MenuVisibilityGroupUpdate(models.TransientModel):
    _name = 'menu.visibility.group.update'
    _description = 'Add Or Remove Groups On Menu Items'

    mode = fields.Selection(
        MODE_SELECTION, string='What To Do', default='add', required=True,
        help='Adding a group narrows an item that had none: from then on only '
             'that group sees it. Removing the last group on an item makes it '
             'visible to everybody again.')
    menu_ids = fields.Many2many(
        'ir.ui.menu', string='Menu Items', required=True,
        help='The menu items to change. Nothing outside this list is touched.')
    group_ids = fields.Many2many(
        'res.groups', string='Groups', required=True)
    include_children = fields.Boolean(
        string='Also Apply To Every Item Below',
        help='Apply the same change to the whole sub-tree of the selected '
             'items. Off by default: the count below tells you how many items '
             'would be affected before you commit to it.')

    target_count = fields.Integer(
        string='Items That Would Change', compute='_compute_preview')
    public_count = fields.Integer(
        string='Items Left With No Group', compute='_compute_preview')
    preview_message = fields.Text(
        string='What Will Happen', compute='_compute_preview')

    result_message = fields.Text(string='Result', readonly=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        context = self.env.context
        if 'menu_ids' in fields_list and context.get('active_model') == 'ir.ui.menu':
            active_ids = context.get('active_ids') or (
                [context['active_id']] if context.get('active_id') else [])
            if active_ids:
                values['menu_ids'] = [(6, 0, list(active_ids))]
        return values

    # ------------------------------------------------------------- helpers ---
    def _check_operator(self):
        """Only a Settings administrator may change menu visibility.

        security/ir.model.access.csv already restricts this wizard to
        base.group_system, and Odoo's own access line on ir.ui.menu gives write
        to that group only. This is the third lock, on the method itself.
        """
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_(
                'Changing menu visibility is reserved to Settings '
                'administrators.'))

    def _target_menus(self):
        """The selected items, plus their sub-tree when asked for."""
        menus = self.menu_ids
        if menus and self.include_children:
            menus |= self.env['ir.ui.menu'].with_context(
                **{'ir.ui.menu.full_list': True}).search(
                    [('id', 'child_of', menus.ids)])
        return menus

    def _resulting_groups(self, menu, groups_field):
        current = menu[groups_field]
        if self.mode == 'remove':
            return current - self.group_ids
        return current | self.group_ids

    @api.depends('menu_ids', 'group_ids', 'mode', 'include_children')
    def _compute_preview(self):
        for wizard in self:
            if not wizard.menu_ids or not wizard.group_ids:
                wizard.target_count = 0
                wizard.public_count = 0
                wizard.preview_message = str(_(
                    'Pick at least one menu item and one group.'))
                continue
            groups_field = menu_groups_field(self.env['ir.ui.menu'])
            changing = 0
            public = 0
            for menu in wizard._target_menus():
                new_groups = wizard._resulting_groups(menu, groups_field)
                if new_groups != menu[groups_field]:
                    changing += 1
                if not new_groups:
                    public += 1
            wizard.target_count = changing
            wizard.public_count = public
            messages = [_(
                '%(changing)s menu item(s) will change; the rest already have '
                'the groups the way you asked.', changing=changing)]
            if public:
                messages.append(_(
                    '%s item(s) will be left with no group at all. An item with '
                    'no group is visible to every user who can reach its parent '
                    'menu and read the model its action opens.', public))
            messages.append(_(
                'Nothing else is touched: no group membership is changed, no '
                'access right and no record rule is edited, and no menu item '
                'is created or deleted.'))
            wizard.preview_message = '\n\n'.join(str(m) for m in messages)

    # -------------------------------------------------------------- action ---
    def action_apply(self):
        """Apply the change, then clear the caches menus are answered from."""
        self.ensure_one()
        self._check_operator()
        if not self.group_ids:
            raise UserError(_('Select at least one group.'))
        menus = self._target_menus()
        if not menus:
            raise UserError(_('Select at least one menu item.'))

        groups_field = menu_groups_field(self.env['ir.ui.menu'])
        changed, unchanged, failures = 0, 0, []
        for menu in menus:
            try:
                # one savepoint per item: a menu that cannot be written - a
                # constraint from another module, say - must not roll back the
                # ones that already worked
                with self.env.cr.savepoint():
                    new_groups = self._resulting_groups(menu, groups_field)
                    if new_groups == menu[groups_field]:
                        unchanged += 1
                        continue
                    menu.write({groups_field: [(6, 0, new_groups.ids)]})
                    changed += 1
            except Exception as error:  # pylint: disable=broad-except
                _logger.warning(
                    'menu_access_visibility: could not update menu %s: %s',
                    menu.id, error)
                failures.append('%s: %s' % (menu.display_name, error))

        # Menu visibility is answered from an ormcache keyed on the USER'S
        # group set, not on the menus. Without this the server keeps handing
        # out the old answer and the change looks like it did nothing.
        clear_menu_caches(self.env)

        lines = [str(_('%s menu item(s) updated.', changed))]
        if unchanged:
            lines.append(str(_(
                '%s item(s) already had the groups you asked for and were left '
                'alone.', unchanged)))
        if failures:
            lines.append(str(_('%s item(s) could not be updated:', len(failures))))
            lines.extend(failures[:20])
        lines.append(str(_(
            'The menu caches were cleared, so the change is effective now. '
            'Reload the interface to redraw your own menu bar.')))
        self.result_message = '\n'.join(lines)

        return {
            'type': 'ir.actions.act_window',
            'name': str(_('Menu Visibility Updated')),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref(
                'menu_access_visibility.view_menu_group_update_result').id,
                'form')],
            'target': 'new',
        }

    def action_reload(self):
        """Redraw the client so the operator's own menu bar picks the change up."""
        self.ensure_one()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
