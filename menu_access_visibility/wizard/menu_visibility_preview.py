# -*- coding: utf-8 -*-
# Part of menu_access_visibility. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError

from ..models.ir_ui_menu import (
    MAX_PREVIEW_LINES,
    menu_groups_field,
    user_group_ids,
    visible_menu_ids,
)

_logger = logging.getLogger(__name__)

SHOW_SELECTION = [
    ('tree', 'Only what the user really sees'),
    ('hidden', 'Only what is hidden from the user'),
    ('all', 'Every menu item, visible or not'),
]


class MenuVisibilityPreview(models.TransientModel):
    _name = 'menu.visibility.preview'
    _description = 'Preview The Menu Of A User'

    user_id = fields.Many2one(
        'res.users', string='User', required=True, ondelete='cascade',
        default=lambda self: self.env.user,
        help='The user whose menu is being previewed. Nothing is done in their '
             'name: the preview only asks Odoo which menu items they may see.')
    show = fields.Selection(
        SHOW_SELECTION, string='Show', default='tree', required=True,
        help='Which lines to list. The counters above always cover the whole '
             'menu tree, whatever this is set to.')
    state = fields.Selection(
        [('draft', 'Not Run'), ('done', 'Done')],
        string='Status', default='draft', readonly=True)

    total_count = fields.Integer(
        string='Menu Items In The Database', readonly=True)
    tree_count = fields.Integer(
        string='Items The User Sees', readonly=True,
        help='Items that pass their own checks AND whose parents all pass '
             'theirs. This is what the menu really draws for that user.')
    allowed_count = fields.Integer(
        string='Items That Pass Their Own Checks', readonly=True,
        help='Items whose groups and action model access allow this user. '
             'Some of them are still not reachable because a parent menu is '
             'hidden - the difference between this number and the one above.')
    hidden_count = fields.Integer(string='Items Hidden', readonly=True)
    truncated = fields.Boolean(
        string='List Truncated', readonly=True,
        help='Ticked when the menu tree is larger than the display cap and '
             'only part of it is listed. The counters stay exact.')
    note = fields.Text(string='Notes', readonly=True)
    line_ids = fields.One2many(
        'menu.visibility.preview.line', 'preview_id', string='Menu Items',
        readonly=True)

    # ------------------------------------------------------------- helpers ---
    def _check_operator(self):
        """Only a Settings administrator may inspect somebody else's menu.

        security/ir.model.access.csv already restricts the models to
        base.group_system; this is the second lock, on the method itself.
        """
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_(
                'Menu visibility preview is reserved to Settings '
                'administrators.'))

    def _collect_notes(self, user, menus, allowed_ids, tree_ids):
        notes = []
        if user.id == SUPERUSER_ID or user.has_group('base.group_system'):
            notes.append(str(_(
                '%s is a Settings administrator, so almost nothing is hidden '
                'from them by model access; only groups placed on the menu '
                'items themselves can still hide something.',
                user.display_name)))
        if user.id == SUPERUSER_ID:
            notes.append(str(_(
                'This is the superuser account: it bypasses access rights '
                'entirely, so treat the answer as "everything".')))
        if not user.active:
            notes.append(str(_('This user is archived and cannot log in.')))
        if hasattr(user, 'share') and user.share:
            notes.append(str(_(
                '%s is a portal or public user. The back end menu is not shown '
                'to them at all, whatever this screen lists.',
                user.display_name)))
        difference = len(allowed_ids) - len(tree_ids)
        if difference > 0:
            notes.append(str(_(
                '%s item(s) would be allowed on their own but are not reachable '
                'because a parent menu is hidden from this user. They are '
                'listed as hidden, with the parent named.', difference)))
        notes.append(str(_(
            'Computed with developer mode OFF. In developer mode Odoo also '
            'shows the items reserved to the technical "Technical Features" '
            'group, so an administrator in developer mode sees more than this.')))
        notes.append(str(_(
            'The answer comes from Odoo itself: '
            'ir.ui.menu._visible_menu_ids() evaluated as this user, plus the '
            'parent chain rule the web client applies when it builds the menu '
            'tree. Nothing here re-implements the visibility rules.')))
        return notes

    # -------------------------------------------------------------- action ---
    def action_preview(self):
        """Fill the result section with one line per menu item."""
        self.ensure_one()
        self._check_operator()
        user = self.user_id
        menu_model = self.env['ir.ui.menu']
        groups_field = menu_groups_field(menu_model)

        # 'ir.ui.menu.full_list' switches off the visibility filter Odoo puts
        # on ir.ui.menu.search: without it this screen would only ever see the
        # menus the ADMINISTRATOR can see, and could not report on the rest.
        menus = menu_model.with_context(**{'ir.ui.menu.full_list': True}).search([])
        menus.mapped(groups_field)
        # the whole tree's actions in one query per action model, instead of
        # one existence check per menu item
        actions = menu_model._mav_actions(menus)
        allowed_ids = visible_menu_ids(self.env, user)
        allowed_ids &= set(menus.ids)
        target_groups = user_group_ids(user)
        access = self.env['ir.model.access'].with_user(user)

        parent_of = {menu.id: menu.parent_id.id for menu in menus}
        names = {menu.id: menu.name for menu in menus}

        def reachable(menu_id):
            """Visible AND every ancestor visible, which is what gets drawn.

            Odoo marks a menu item visible on its own merits, then the web
            client builds the tree from the root down and drops whatever it
            cannot attach to a visible application. A child under a hidden
            parent is therefore allowed but never drawn.
            """
            seen = set()
            node = menu_id
            while node and node not in seen:
                if node not in allowed_ids:
                    return False
                seen.add(node)
                node = parent_of.get(node)
            return True

        def blocking_parent(menu_id):
            seen = set()
            node = parent_of.get(menu_id)
            while node and node not in seen:
                if node not in allowed_ids:
                    return names.get(node) or _('Unnamed menu')
                seen.add(node)
                node = parent_of.get(node)
            return ''

        def depth(menu_id):
            seen, node, level = set(), parent_of.get(menu_id), 0
            while node and node not in seen:
                seen.add(node)
                level += 1
                node = parent_of.get(node)
            return level

        tree_ids = {menu.id for menu in menus if reachable(menu.id)}

        self.line_ids.unlink()
        values = []
        truncated = False
        for menu in menus:
            is_allowed = menu.id in allowed_ids
            in_tree = menu.id in tree_ids
            if self.show == 'tree' and not in_tree:
                continue
            if self.show == 'hidden' and in_tree:
                continue
            own = menu[groups_field]
            _action, model_name, action_state = actions.get(
                menu.id, (None, '', 'folder'))
            values.append({
                'preview_id': self.id,
                'menu_id': menu.id,
                'path': menu._get_full_name(),
                'level': depth(menu.id),
                'group_names': ', '.join(sorted(own.mapped('display_name'))),
                'is_allowed': is_allowed,
                'in_menu_tree': in_tree,
                'reason': self._explain(
                    action_state, own, target_groups, is_allowed, in_tree,
                    model_name, access, blocking_parent(menu.id)),
            })
            if len(values) >= MAX_PREVIEW_LINES and menu != menus[-1]:
                # only a list that really stopped short is truncated: a tree of
                # exactly MAX_PREVIEW_LINES items is complete
                truncated = True
                break

        self.env['menu.visibility.preview.line'].create(values)
        self.write({
            'state': 'done',
            'total_count': len(menus),
            'allowed_count': len(allowed_ids),
            'tree_count': len(tree_ids),
            'hidden_count': len(menus) - len(tree_ids),
            'truncated': truncated,
            'note': '\n'.join(
                self._collect_notes(user, menus, allowed_ids, tree_ids)),
        })
        return False

    def _explain(self, action_state, own_groups, target_groups, is_allowed,
                 in_tree, model_name, access, parent_name):
        """Why this item is or is not on that user's menu, in one sentence."""
        if not is_allowed:
            if own_groups and not (set(own_groups.ids) & target_groups):
                return str(_(
                    'Hidden: the item is limited to %s and the user is in none '
                    'of them.', ', '.join(sorted(own_groups.mapped('display_name')))))
            if model_name:
                try:
                    readable = access.check(model_name, 'read', False)
                except Exception as error:  # pylint: disable=broad-except
                    # never fall through to a confident wrong diagnosis: say
                    # that the check itself could not be made
                    _logger.warning(
                        'menu_access_visibility: read check on %s failed: %s',
                        model_name, error)
                    return str(_(
                        'Hidden, and the read access check on %s could not be '
                        'made, so the exact reason is unconfirmed.',
                        model_name))
                if not readable:
                    return str(_(
                        'Hidden: the user has no read access on %s, the model '
                        'of this item\'s action.', model_name))
            if action_state == 'missing':
                return str(_(
                    'Hidden: the action this item points at is no longer in '
                    'the database.'))
            if action_state == 'unreadable':
                return str(_(
                    'Hidden, and this item\'s action could not be read from '
                    'here, so the exact reason is unconfirmed.'))
            if action_state == 'folder':
                return str(_(
                    'Hidden: it is a folder and no item under it is visible to '
                    'this user.'))
            return str(_('Hidden by the menu visibility computation.'))
        if not in_tree:
            return str(_(
                'Hidden: the item itself would be allowed, but the parent menu '
                '"%s" is hidden from this user, so the tree never reaches it.',
                parent_name or _('above it')))
        if own_groups:
            matching = own_groups.filtered(lambda g: g.id in target_groups)
            return str(_(
                'Visible: the user is in %s.',
                ', '.join(sorted(matching.mapped('display_name')))
                or _('a group that grants it')))
        return str(_('Visible: no group restricts this item.'))


class MenuVisibilityPreviewLine(models.TransientModel):
    _name = 'menu.visibility.preview.line'
    _description = 'Previewed Menu Item'
    _order = 'path, id'

    preview_id = fields.Many2one(
        'menu.visibility.preview', string='Preview', required=True,
        ondelete='cascade', index=True)
    menu_id = fields.Many2one(
        'ir.ui.menu', string='Menu Item', ondelete='cascade')
    path = fields.Char(string='Menu Path')
    level = fields.Integer(string='Depth')
    group_names = fields.Char(
        string='Groups On This Item',
        help='The groups recorded on the item itself. Empty means the item '
             'carries no restriction of its own.')
    is_allowed = fields.Boolean(
        string='Passes Its Own Checks',
        help='Ticked when the groups on the item and the read access on its '
             'action model allow this user.')
    in_menu_tree = fields.Boolean(
        string='On The Menu',
        help='Ticked when the item is really drawn for this user: it passes '
             'its own checks and so does every menu above it.')
    reason = fields.Char(string='Why')
