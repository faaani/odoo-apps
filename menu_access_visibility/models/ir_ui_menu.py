# -*- coding: utf-8 -*-
# Part of menu_access_visibility. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
from collections import defaultdict

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Where an action keeps the model it works on. Odoo does NOT read groups from
# the action itself when it decides whether a menu item shows: for a menu that
# carries an action it checks READ access on the action's model. That is why
# this mapping - and not action.groups_id - is what "who sees this menu" has to
# look at.
ACTION_MODEL_FIELD = {
    'ir.actions.act_window': 'res_model',
    'ir.actions.report': 'model',
    'ir.actions.server': 'model_name',
}

VISIBILITY_SELECTION = [
    ('everyone', 'Everyone'),
    ('own', 'Groups on this item'),
    ('parent', 'A parent menu'),
    ('own_parent', 'This item and a parent'),
]

# A menu tree is small (a full Odoo install is around 700 items), but a
# preview must never turn into an unbounded query either.
MAX_PREVIEW_LINES = 3000


def menu_groups_field(model):
    """Name of the many2many holding a menu's groups.

    19.0 renamed ``ir.ui.menu.groups_id`` to ``group_ids``. Reading the name
    out of ``_fields`` keeps a single code path for 14.0 through 19.0.
    """
    return 'group_ids' if 'group_ids' in model._fields else 'groups_id'


def user_group_ids(user):
    """The ids of every group ``user`` effectively holds, implied ones included.

    14.0-17.0 flatten implied groups into ``groups_id`` when a user is saved.
    18.0 and 19.0 expose ``_get_group_ids()``, which returns the transitive
    closure; 19.0 needs it, because there ``group_ids`` holds only the groups
    somebody ticked by hand.
    """
    if hasattr(user, '_get_group_ids'):  # 18.0+
        return set(user._get_group_ids())
    return set(user.groups_id.ids)


def clear_menu_caches(env):
    """Drop the caches Odoo answers menu visibility from.

    ``ir.ui.menu._visible_menu_ids`` is an ormcache keyed on the *user's group
    set*, not on the menus themselves, and ``load_menus`` is cached per user.
    Change the groups of a menu without clearing them and the change looks like
    it did not happen: the server keeps answering from the cached set until the
    worker is restarted. Odoo's own ``ir.ui.menu.write`` clears the cache, so
    this call is a second lock - it also covers the paths that do not, such as
    writing the reverse many-to-many ``res.groups.menu_access`` on 16.0.

    In a multi-worker deployment the other workers pick the invalidation up
    when the transaction commits, through the registry signalling Odoo already
    uses for this.
    """
    registry = env.registry
    if hasattr(registry, 'clear_cache'):  # 17.0+
        registry.clear_cache()
    elif hasattr(registry, 'clear_caches'):  # 14.0 - 16.0
        registry.clear_caches()
    else:  # pragma: no cover - no supported series lands here
        env['ir.ui.menu'].clear_caches()


def visible_menu_ids(env, user):
    """The ids Odoo itself considers visible for ``user``, debug mode off.

    ``_filter_visible_menus`` would read the debug flag off the *operator's*
    own session, which would quietly add the developer-only menus to somebody
    else's preview. Asking ``_visible_menu_ids(False)`` pins the answer to what
    that user sees with developer mode off.
    """
    menu = env['ir.ui.menu'].with_user(user)
    return set(menu._visible_menu_ids(False))


def action_model_name(action):
    """The model an action works on, or '' when it has none (act_url, client)."""
    field_name = ACTION_MODEL_FIELD.get(action._name)
    if not field_name or field_name not in action._fields:
        return ''
    return action[field_name] or ''


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    # Every field below carries groups='base.group_system'. ir.ui.menu itself
    # grants read to base.group_user, so without it any internal user could
    # read back the whole menu structure and the groups guarding each item -
    # which is exactly the information this module exists to protect. The
    # views are bound to this module's administrator-only action, so nothing
    # in the interface depends on a wider audience.
    mav_path = fields.Char(
        string='Menu Path', compute='_compute_mav_visibility',
        groups='base.group_system',
        help='Where this item sits in the menu tree, from the application '
             'down to the item itself.')
    mav_level = fields.Integer(
        string='Depth', compute='_compute_mav_visibility',
        groups='base.group_system',
        help='0 for an application (a top level menu), 1 for its direct '
             'children, and so on.')
    mav_own_groups = fields.Char(
        string='Groups On This Item', compute='_compute_mav_visibility',
        groups='base.group_system',
        help='The groups recorded on this menu item itself. Empty means the '
             'item carries no restriction of its own.')
    mav_parent_groups = fields.Char(
        string='Groups Required By A Parent', compute='_compute_mav_visibility',
        groups='base.group_system',
        help='Groups a parent menu requires. A menu item is only drawn inside '
             'its parent, so a user excluded from the parent never reaches the '
             'child either, whatever the child says.')
    mav_action_model = fields.Char(
        string='Action Model', compute='_compute_mav_visibility',
        groups='base.group_system',
        help="The model this item's action opens. Empty for a folder, for a "
             'URL action and for a client action.')
    mav_action_groups = fields.Char(
        string='Read Access On That Model', compute='_compute_mav_visibility',
        groups='base.group_system',
        help='The groups an access control line grants read on the action '
             'model to. When a menu item carries an action, Odoo hides the '
             'item from anybody who cannot read that model.')
    mav_visibility = fields.Selection(
        VISIBILITY_SELECTION, string='Restricted By',
        compute='_compute_mav_visibility',
        groups='base.group_system',
        help='Everyone: no group anywhere on the item or its parents. '
             'Otherwise: where the restriction comes from.')
    mav_summary = fields.Char(
        string='Who Sees This Menu', compute='_compute_mav_visibility',
        groups='base.group_system',
        help='One line answer to "who sees this menu?". The full reasoning is '
             'on the form view of the item.')
    mav_explanation = fields.Text(
        string='Visibility Explained', compute='_compute_mav_visibility',
        groups='base.group_system')

    # ------------------------------------------------------------- helpers ---
    def _mav_ancestor_ids(self):
        """Ancestor ids of this menu, nearest parent first."""
        self.ensure_one()
        path = self.parent_path or ''
        if path:
            # parent_path is '1/5/12/' - the whole chain, own id included,
            # already in the table: no recursive query needed.
            ids = [int(part) for part in path.split('/') if part]
            if ids and ids[-1] == self.id:
                ids = ids[:-1]
            return list(reversed(ids))
        # a record being created in a form has no parent_path yet
        ids, node = [], self.parent_id
        while node and node.id not in ids:
            ids.append(node.id)
            node = node.parent_id
        return ids

    @api.model
    def _mav_actions(self, menus):
        """{menu id: (action record or None, action model name, state)}.

        ``action`` is a Reference field, so reading it hands back a one-record
        recordset per menu: checking each with ``exists()`` would be one query
        per row, which a 700-item menu tree cannot afford. The references are
        grouped by model and resolved in one query per model instead - the same
        trick Odoo's own menu loading uses.

        The state is what keeps this screen honest. "No action at all" and "I
        could not read the action" would otherwise render as the same sentence,
        and on an access-audit screen a confident wrong answer is worse than an
        admitted gap:

        * ``folder``     - the item carries no action reference
        * ``missing``    - it points at a record that is no longer there
        * ``ok``         - resolved; the model name is filled in when it has one
        * ``unreadable`` - the reference could not be resolved at all
        """
        references = {}
        unreadable = set()
        ids_by_model = defaultdict(set)
        for menu in menus:
            try:
                action = menu.action
            except Exception:  # pylint: disable=broad-except
                # a Reference to a model whose module was uninstalled
                _logger.warning(
                    'menu_access_visibility: menu %s has an unreadable action '
                    'reference', menu.id)
                unreadable.add(menu.id)
                continue
            if not action:
                continue
            references[menu.id] = (action._name, action.id)
            ids_by_model[action._name].add(action.id)

        existing = {}
        failed_models = set()
        for model_name, action_ids in ids_by_model.items():
            try:
                model = self.env[model_name]
                # exists() is a plain SELECT id: it answers "is there such a
                # row", it does not widen anything and needs no sudo()
                records = model.browse(sorted(action_ids)).exists()
                field_name = ACTION_MODEL_FIELD.get(model_name)
                if field_name and field_name in model._fields:
                    records.mapped(field_name)  # one prefetch for the batch
                for action in records:
                    existing[(model_name, action.id)] = action
            except Exception:  # pylint: disable=broad-except
                # most often no read access on the action model; never report
                # the menus concerned as plain folders because of it
                _logger.warning(
                    'menu_access_visibility: cannot resolve %s actions',
                    model_name)
                failed_models.add(model_name)

        result = {}
        for menu in menus:
            reference = references.get(menu.id)
            if menu.id in unreadable:
                result[menu.id] = (None, '', 'unreadable')
            elif not reference:
                result[menu.id] = (None, '', 'folder')
            elif reference[0] in failed_models:
                result[menu.id] = (None, '', 'unreadable')
            else:
                action = existing.get(reference)
                if action is None:
                    result[menu.id] = (None, '', 'missing')
                else:
                    result[menu.id] = (action, action_model_name(action), 'ok')
        return result

    @api.model
    def _mav_model_read_groups(self, model_names):
        """{model: (group names granted read, granted to everybody)}.

        One search over ``ir.model.access`` for the whole batch. Archived
        access lines are left out, exactly as Odoo's own check does.
        """
        result = {name: (set(), False) for name in model_names}
        if not model_names:
            return result
        rows = self.env['ir.model.access'].search_read(
            [('model_id.model', 'in', list(model_names)),
             ('perm_read', '=', True)],
            ['model_id', 'group_id'])
        # model_id is read as (id, "model.name (Label)") - resolve it properly
        model_by_id = {
            model.id: model.model
            for model in self.env['ir.model'].browse(
                {row['model_id'][0] for row in rows if row['model_id']})
        }
        for row in rows:
            model_name = model_by_id.get(row['model_id'] and row['model_id'][0])
            if model_name not in result:
                continue
            names, everybody = result[model_name]
            if row['group_id']:
                names.add(row['group_id'][1])
            else:
                # an access line with no group grants the permission to every
                # user, so no group can be named as "the" holder of it
                everybody = True
            result[model_name] = (names, everybody)
        return result

    # ------------------------------------------------------------- compute ---
    @api.depends(lambda self: self._mav_depends())
    def _compute_mav_visibility(self):
        groups_field = menu_groups_field(self)
        # ancestors of the whole batch, resolved once and in one browse, so
        # that a list of 80 menu items is not 80 walks up the tree
        ancestors_of = {}
        ancestor_ids = set()
        for menu in self:
            chain = [menu_id for menu_id in menu._mav_ancestor_ids()
                     if isinstance(menu_id, int)]
            ancestors_of[menu.id] = chain
            ancestor_ids.update(chain)
        ancestors = self.browse(sorted(ancestor_ids - set(self.ids)))
        family = self | ancestors
        family.mapped(groups_field)  # prefetch every group link at once
        family.mapped('name')

        actions = self._mav_actions(self)
        model_names = {
            model_name for _action, model_name, _state in actions.values()
            if model_name and model_name in self.env}
        access_by_model = self._mav_model_read_groups(model_names)

        for menu in self:
            own = menu[groups_field]
            own_names = sorted(own.mapped('display_name'))
            chain = ancestors_of.get(menu.id, [])
            parent_requirements = []
            for ancestor_id in chain:
                ancestor = self.browse(ancestor_id)
                ancestor_groups = ancestor[groups_field]
                if ancestor_groups:
                    parent_requirements.append(
                        (ancestor.name or _('Unnamed menu'),
                         sorted(ancestor_groups.mapped('display_name'))))

            _action, model_name, action_state = actions.get(
                menu.id, (None, '', 'folder'))
            read_names, read_everybody = access_by_model.get(
                model_name, (set(), False))

            menu.mav_path = menu._get_full_name()
            menu.mav_level = len(chain)
            menu.mav_own_groups = ', '.join(own_names)
            menu.mav_parent_groups = '; '.join(
                '%s: %s' % (name, ', '.join(groups))
                for name, groups in parent_requirements)
            menu.mav_action_model = model_name
            if action_state == 'unreadable':
                menu.mav_action_groups = str(
                    _('Unknown: the action could not be read here'))
            elif not model_name:
                menu.mav_action_groups = ''
            elif read_everybody:
                menu.mav_action_groups = str(_('Every user'))
            elif read_names:
                menu.mav_action_groups = ', '.join(sorted(read_names))
            else:
                menu.mav_action_groups = str(
                    _('Nobody: no access line grants read'))

            if own_names and parent_requirements:
                menu.mav_visibility = 'own_parent'
            elif own_names:
                menu.mav_visibility = 'own'
            elif parent_requirements:
                menu.mav_visibility = 'parent'
            else:
                menu.mav_visibility = 'everyone'

            menu.mav_summary = menu._mav_build_summary(
                own_names, parent_requirements, model_name, action_state)
            menu.mav_explanation = menu._mav_build_explanation(
                own_names, parent_requirements, model_name, read_names,
                read_everybody, action_state)

    @api.model
    def _mav_depends(self):
        """Dependencies of the visibility compute, with the right field name.

        The many-to-many is ``groups_id`` up to 18.0 and ``group_ids`` on 19.0,
        so the dependency list is built from the registry instead of being
        hard-coded. Ancestors are followed three levels up, which covers the
        application / section / item shape of every real menu tree; a change
        further up than that is picked up on the next read.
        """
        groups_field = menu_groups_field(self)
        return (
            'name', 'action', 'parent_id', 'parent_path', groups_field,
            'parent_id.name', 'parent_id.%s' % groups_field,
            'parent_id.parent_id.name', 'parent_id.parent_id.%s' % groups_field,
            'parent_id.parent_id.parent_id.name',
            'parent_id.parent_id.parent_id.%s' % groups_field,
        )

    def _mav_build_summary(self, own_names, parent_requirements, model_name,
                           action_state):
        """The one-line answer shown in the list.

        Assembled from whole sentences rather than from fragments: a translator
        handed " + read access on %s" has no way to know what it attaches to.
        Every call to _() is wrapped in str() so a plain string reaches the
        Char field whichever translation helper the series returns.
        """
        clauses = []
        if own_names:
            clauses.append(str(_('Members of %s.', ', '.join(own_names))))
        else:
            clauses.append(str(_('Everyone: no group on this item.')))
        if parent_requirements:
            clauses.append(str(_(
                'The parent menu "%(menu)s" needs %(groups)s.',
                menu=parent_requirements[0][0],
                groups=', '.join(parent_requirements[0][1]))))
            if len(parent_requirements) > 1:
                clauses.append(str(_(
                    '%s more parent menu(s) restrict it as well.',
                    len(parent_requirements) - 1)))
        if model_name:
            clauses.append(str(_('Read access on %s is required too.',
                                 model_name)))
        elif action_state == 'unreadable':
            clauses.append(str(_(
                'Its action could not be read here, so model access was not '
                'checked.')))
        elif action_state == 'missing':
            clauses.append(str(_('Its action no longer exists.')))
        return ' '.join(clauses)

    def _mav_build_explanation(self, own_names, parent_requirements, model_name,
                               read_names, read_everybody, action_state):
        """The paragraph shown on the form view."""
        lines = []
        if own_names:
            lines.append(str(_(
                'This item is limited to the group(s) %s. A user in none of '
                'them never sees it.', ', '.join(own_names))))
        else:
            lines.append(str(_(
                'This item carries no group of its own, so it puts no group '
                'restriction on anybody.')))

        for name, groups in parent_requirements:
            lines.append(str(_(
                'It is drawn inside the parent menu "%(menu)s", which is '
                'limited to %(groups)s. A user outside those groups does not '
                'see the parent, and therefore never reaches this item '
                'either - even though nothing on this item says so.',
                menu=name, groups=', '.join(groups))))
        if not parent_requirements:
            lines.append(str(_('No parent menu adds a group restriction.')))

        if model_name:
            if read_everybody:
                who = str(_('every user, through an access line with no group'))
            elif read_names:
                who = ', '.join(sorted(read_names))
            else:
                who = str(_('nobody: no access control line grants read on it'))
            lines.append(str(_(
                'The item opens an action on the model %(model)s. Odoo hides a '
                'menu item from any user who cannot READ its action model, '
                'whatever groups the item carries. Read on %(model)s is '
                'granted to: %(who)s.', model=model_name, who=who)))
        elif action_state == 'ok':
            lines.append(str(_(
                'The action of this item works on no model, so model access '
                'does not restrict it.')))
        elif action_state == 'missing':
            lines.append(str(_(
                'This item points at an action that is no longer in the '
                'database. Odoo skips such an item when it builds the menu, so '
                'nobody sees it until the action is restored.')))
        elif action_state == 'unreadable':
            lines.append(str(_(
                'This item carries an action that could not be read from here, '
                'so its model access could NOT be checked and is not part of '
                'the answer above. Open this screen as a Settings '
                'administrator to get the complete picture.')))
        else:
            lines.append(str(_(
                'This item opens no action: it is a folder. Odoo only shows a '
                'folder when at least one item below it is visible, so an '
                'empty-for-this-user folder disappears on its own.')))
        lines.append(str(_(
            'Answered from: the groups on the item, the groups on every parent '
            'menu, and the read access lines on the action model - the three '
            'inputs Odoo itself uses in ir.ui.menu._visible_menu_ids(). Use '
            'Preview A User Menu to see the result for one real user.')))
        return '\n\n'.join(lines)

    # --------------------------------------------------------------- write ---
    def write(self, values):
        """Clear the menu caches whenever the group many-to-many is touched.

        Odoo's ``ir.ui.menu.write`` already clears them, and clears them for
        every write. This override changes no behaviour there; it is here so
        that the guarantee this module makes - "change the groups and the
        change takes effect" - does not depend on an implementation detail of
        the series it runs on.
        """
        result = super().write(values)
        if menu_groups_field(self) in values:
            clear_menu_caches(self.env)
        return result


class ResGroups(models.Model):
    _inherit = 'res.groups'

    @api.model_create_multi
    def create(self, vals_list):
        """Same guarantee when a group is created with menus already attached.

        That path goes through neither ``ir.ui.menu.write`` nor the override
        below, and on 19.0 core clears only the 'groups' cache on group
        creation - not the one ``_visible_menu_ids`` lives in.
        """
        groups = super().create(vals_list)
        if any('menu_access' in values for values in vals_list):
            clear_menu_caches(self.env)
        return groups

    def write(self, vals):
        """Clear the menu caches when menus are attached from the group side.

        ``res.groups.menu_access`` is the same table as ``ir.ui.menu.groups_id``
        read backwards, but writing it goes through ``res.groups.write``, which
        on 16.0 does not clear the menu ormcache - the menu then keeps showing
        (or keeps hiding) until the worker restarts.
        """
        result = super().write(vals)
        if 'menu_access' in vals:
            clear_menu_caches(self.env)
        return result
