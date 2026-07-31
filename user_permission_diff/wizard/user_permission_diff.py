# -*- coding: utf-8 -*-
# Part of user_permission_diff. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError

# One row per model and per side in the "what does the difference actually
# grant" table. A diff between two ordinary users is a handful of models; a diff
# between a fresh user and a full administrator is the whole catalogue, so the
# table is capped and the wizard says so instead of silently truncating.
MODEL_LINE_LIMIT = 200


def flush(env):
    """Push pending ORM writes to the database before reading it with SQL."""
    # 16.0 introduced Environment.flush_all(); 14.0/15.0 flush from any model.
    if hasattr(env, 'flush_all'):
        env.flush_all()
    else:
        env['res.users'].flush()


def user_groups_field(env):
    """Name of the groups field of res.users.

    19.0 renamed ``res.users.groups_id`` to ``res.users.group_ids``. Resolving it
    from the registry keeps one source file working on every series.
    """
    return 'group_ids' if 'group_ids' in env['res.users']._fields else 'groups_id'


def assigned_group_ids(env, user):
    """Ids of the groups the user is *directly* assigned."""
    return set(user[user_groups_field(env)].ids)


def expand_group_ids(env, group_ids):
    """Transitive closure of ``res.groups.implied_ids`` over a set of groups.

    A user is a member of every group they are assigned, plus everything those
    groups imply, transitively - that is what Odoo checks in ``has_group``. The
    recursive term walks the implication table; UNION (not UNION ALL) discards
    rows already seen, so a cycle in the graph terminates instead of looping for
    ever. Reading the relation table directly is safe here: it holds no data of
    its own and the whole tool is restricted to Settings users.
    """
    ids = tuple(sorted(set(group_ids)))
    if not ids:
        return set()
    flush(env)
    env.cr.execute("""
        WITH RECURSIVE closure(id) AS (
                SELECT g.id
                  FROM res_groups g
                 WHERE g.id IN %s
            UNION
                SELECT rel.hid
                  FROM closure c
                  JOIN res_groups_implied_rel rel ON rel.gid = c.id
        )
        SELECT id FROM closure
    """, (ids,))
    return {row[0] for row in env.cr.fetchall()}


def access_map(env, group_ids):
    """{model id: (read, write, create, unlink)} granted to a set of groups.

    Aggregated in one statement rather than by browsing ir.model.access row by
    row. Access lines that carry no group are granted by Odoo to every user, so
    they are part of what *both* sides already have and are included on both.
    """
    ids = tuple(sorted(set(group_ids))) or (0,)
    flush(env)
    env.cr.execute("""
        SELECT a.model_id,
               BOOL_OR(a.perm_read), BOOL_OR(a.perm_write),
               BOOL_OR(a.perm_create), BOOL_OR(a.perm_unlink)
          FROM ir_model_access a
         WHERE a.active
           AND (a.group_id IS NULL OR a.group_id IN %s)
      GROUP BY a.model_id
    """, (ids,))
    return {row[0]: (row[1], row[2], row[3], row[4]) for row in env.cr.fetchall()}


def group_category_name(group):
    """Application (14.0-18.0) or privilege (19.0) a group belongs to."""
    if 'privilege_id' in group._fields:
        return group.privilege_id.display_name or ''
    return group.category_id.display_name or ''


def groups_to_grant(env, source_user, target_user):
    """The groups a copy would really write on the target user.

    Only the groups the *source* is directly assigned are ever written: adding
    them gives the target every group the source has effectively, because the
    implied ones follow from the assignment. Anything the target already has -
    assigned or implied - is left out, so the write is the smallest one that
    closes the gap.
    """
    if not source_user or not target_user:
        return env['res.groups'].browse()
    missing = assigned_group_ids(env, source_user) - expand_group_ids(
        env, assigned_group_ids(env, target_user))
    return env['res.groups'].browse(sorted(missing)).exists()


def check_actor(env):
    """The caller must be a Settings / Administration user.

    Checked again every time the module is about to act, not only when the
    dialog is opened: copying groups is a privilege escalation vector and a
    button name can be replayed over RPC.
    """
    if not env.user.has_group('base.group_system'):
        raise AccessError(_(
            'Comparing or copying user permissions is reserved to users with '
            'Settings / Administration access.'))


def check_target(env, target):
    """Refuse to write on the accounts that must never be changed this way."""
    if not target:
        raise UserError(_('Choose the user the groups should be copied to.'))
    if target.id == SUPERUSER_ID:
        raise UserError(_(
            'User id 1 is the superuser: it already bypasses every access right '
            'and this module never writes to it.'))
    admin = env.ref('base.user_admin', raise_if_not_found=False)
    if admin and target.id == admin.id:
        raise UserError(_(
            'The default administrator account is never modified by this '
            'module. If it really has to change, edit it from Settings / Users.'))


class UserPermissionDiff(models.TransientModel):
    _name = 'user.permission.diff'
    _description = 'Compare User Permissions'

    user_a_id = fields.Many2one(
        'res.users', string='User A', required=True, ondelete='cascade',
        help='The reference user - the one whose rights are being copied from.')
    user_b_id = fields.Many2one(
        'res.users', string='User B', required=True, ondelete='cascade',
        help='The user being compared with, and the one a copy would write to.')
    compare_mode = fields.Selection(
        [('effective', 'Effective groups (implied groups expanded)'),
         ('assigned', 'Assigned groups only')],
        string='Compare', required=True, default='effective',
        help='Effective: every group the user is assigned plus every group '
             'those imply, transitively - this is what Odoo actually checks.\n'
             'Assigned: only the groups ticked on the user form.')

    notice = fields.Text(string='Summary', readonly=True)
    only_a_title = fields.Char(readonly=True)
    only_b_title = fields.Char(readonly=True)
    shared_title = fields.Char(readonly=True)
    only_a_count = fields.Integer(string='Only A', readonly=True)
    only_b_count = fields.Integer(string='Only B', readonly=True)
    shared_count = fields.Integer(string='Shared Groups', readonly=True)
    copy_count = fields.Integer(
        string='Groups a copy would grant', readonly=True,
        help='How many groups would really be written on User B: the groups '
             'User A is directly assigned and User B does not have.')
    computed = fields.Boolean(
        string='Comparison Done', readonly=True,
        help='Ticked once the two users have been compared.')

    line_ids = fields.One2many(
        'user.permission.diff.line', 'diff_id', string='All Groups', readonly=True)
    only_a_line_ids = fields.One2many(
        'user.permission.diff.line', 'diff_id', string='Only User A',
        domain=[('side', '=', 'only_a')], readonly=True)
    only_b_line_ids = fields.One2many(
        'user.permission.diff.line', 'diff_id', string='Only User B',
        domain=[('side', '=', 'only_b')], readonly=True)
    shared_line_ids = fields.One2many(
        'user.permission.diff.line', 'diff_id', string='Shared',
        domain=[('side', '=', 'shared')], readonly=True)
    model_line_ids = fields.One2many(
        'user.permission.diff.model.line', 'diff_id',
        string='Model Permissions', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super(UserPermissionDiff, self).default_get(fields_list)
        # Opened from the Users list with one or two users ticked.
        if self.env.context.get('active_model') == 'res.users':
            ids = list(self.env.context.get('active_ids') or [])
            if not ids and self.env.context.get('active_id'):
                ids = [self.env.context['active_id']]
            if ids and 'user_a_id' in fields_list and not res.get('user_a_id'):
                res['user_a_id'] = ids[0]
            if len(ids) > 1 and 'user_b_id' in fields_list and not res.get('user_b_id'):
                res['user_b_id'] = ids[1]
        return res

    # ------------------------------------------------------------------ actions
    def action_compare(self):
        self.ensure_one()
        check_actor(self.env)
        if not self.user_a_id or not self.user_b_id:
            raise UserError(_('Choose the two users to compare.'))
        if self.user_a_id == self.user_b_id:
            raise UserError(_(
                'Choose two different users: comparing a user with themselves '
                'always yields an empty difference.'))
        self._build_lines()
        return self._reopen()

    def action_open_copy(self):
        """Open the confirmation dialog. Nothing is written by this method."""
        self.ensure_one()
        check_actor(self.env)
        # the refusal to touch the superuser and the default administrator comes
        # first: it must not be hidden behind an "empty selection" message
        check_target(self.env, self.user_b_id)
        if self.user_a_id == self.user_b_id:
            raise UserError(_('Choose two different users first.'))
        groups = groups_to_grant(self.env, self.user_a_id, self.user_b_id)
        if not groups:
            raise UserError(_(
                '%(target)s already has every group %(source)s is assigned: '
                'there is nothing to copy.',
            ) % {'target': self.user_b_id.display_name,
                 'source': self.user_a_id.display_name})
        confirm = self.env['user.permission.diff.copy'].create({
            'diff_id': self.id,
            'source_user_id': self.user_a_id.id,
            'target_user_id': self.user_b_id.id,
            'group_ids': [(6, 0, groups.ids)],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Copy Groups'),
            'res_model': confirm._name,
            'res_id': confirm.id,
            'view_mode': 'form',
            'views': [(self.env.ref(
                'user_permission_diff.view_user_permission_diff_copy_form').id, 'form')],
            'target': 'new',
        }

    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Compare User Permissions'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref(
                'user_permission_diff.view_user_permission_diff_form').id, 'form')],
            'target': 'new',
        }

    # ------------------------------------------------------------- computation
    def _build_lines(self):
        """(Re)build the three group columns and the model permission summary."""
        self.ensure_one()
        check_actor(self.env)
        self.line_ids.unlink()
        self.model_line_ids.unlink()

        a_assigned = assigned_group_ids(self.env, self.user_a_id)
        b_assigned = assigned_group_ids(self.env, self.user_b_id)
        a_effective = expand_group_ids(self.env, a_assigned)
        b_effective = expand_group_ids(self.env, b_assigned)
        effective = self.compare_mode == 'effective'
        a_shown = a_effective if effective else a_assigned
        b_shown = b_effective if effective else b_assigned

        self._create_group_lines(
            a_shown, b_shown, a_assigned, b_assigned, a_effective, b_effective)
        truncated = self._create_model_lines(a_effective, b_effective)

        counts = {side: len(self.line_ids.filtered(lambda l, s=side: l.side == s))
                  for side in ('only_a', 'only_b', 'shared')}
        copy_groups = groups_to_grant(self.env, self.user_a_id, self.user_b_id)
        mode = _('effective') if effective else _('assigned')
        self.write({
            'computed': True,
            'only_a_count': counts['only_a'],
            'only_b_count': counts['only_b'],
            'shared_count': counts['shared'],
            'copy_count': len(copy_groups),
            'only_a_title': _('Only %(user)s: %(count)s %(mode)s group(s)') % {
                'user': self.user_a_id.display_name, 'count': counts['only_a'],
                'mode': mode},
            'only_b_title': _('Only %(user)s: %(count)s %(mode)s group(s)') % {
                'user': self.user_b_id.display_name, 'count': counts['only_b'],
                'mode': mode},
            'shared_title': _('Shared by both: %(count)s %(mode)s group(s)') % {
                'count': counts['shared'], 'mode': mode},
            'notice': self._build_notice(counts, len(copy_groups), truncated),
        })

    def _create_group_lines(self, a_shown, b_shown, a_assigned, b_assigned,
                            a_effective, b_effective):
        def source(group_id, assigned, effective_ids):
            if group_id in assigned:
                return 'assigned'
            if group_id in effective_ids:
                return 'implied'
            return 'none'

        groups = self.env['res.groups'].browse(sorted(a_shown | b_shown)).exists()
        vals = []
        for group in groups:
            in_a, in_b = group.id in a_shown, group.id in b_shown
            vals.append({
                'diff_id': self.id,
                'group_id': group.id,
                'group_name': group.display_name or group.name,
                'category_name': group_category_name(group),
                'side': 'shared' if in_a and in_b else ('only_a' if in_a else 'only_b'),
                'source_a': source(group.id, a_assigned, a_effective),
                'source_b': source(group.id, b_assigned, b_effective),
                'to_copy': in_a and not in_b and group.id in a_assigned,
            })
        if vals:
            self.env['user.permission.diff.line'].create(vals)

    def _create_model_lines(self, a_effective, b_effective):
        """One row per model whose permissions one side has and the other has not.

        Always computed on the *effective* groups: what a user may do is decided
        by the union of their groups' access lines, whether the group was ticked
        on the user form or implied by another one.
        """
        a_access = access_map(self.env, a_effective)
        b_access = access_map(self.env, b_effective)
        truncated = False
        vals = []
        for side, mine, theirs, user in (
                ('only_a', a_access, b_access, self.user_a_id),
                ('only_b', b_access, a_access, self.user_b_id)):
            gains = []
            for model_id, perms in mine.items():
                other = theirs.get(model_id, (False, False, False, False))
                gain = tuple(bool(p) and not bool(o) for p, o in zip(perms, other))
                if any(gain):
                    gains.append((model_id, gain))
            names = {m.id: m.model for m in
                     self.env['ir.model'].browse([g[0] for g in gains]).exists()}
            gains = sorted((g for g in gains if g[0] in names),
                           key=lambda g: names[g[0]])
            if len(gains) > MODEL_LINE_LIMIT:
                truncated = True
                gains = gains[:MODEL_LINE_LIMIT]
            for model_id, gain in gains:
                vals.append({
                    'diff_id': self.id,
                    'side': side,
                    'side_label': _('%s only') % user.display_name,
                    'model_id': model_id,
                    'model_name': names[model_id],
                    'perm_read': gain[0],
                    'perm_write': gain[1],
                    'perm_create': gain[2],
                    'perm_unlink': gain[3],
                    'rights_code': ''.join(
                        letter if granted else '-'
                        for letter, granted in zip('RWCD', gain)),
                })
        if vals:
            self.env['user.permission.diff.model.line'].create(vals)
        return truncated

    def _build_notice(self, counts, copy_count, truncated):
        lines = []
        if self.compare_mode == 'effective':
            lines.append(_(
                'The three columns show EFFECTIVE groups: every group the user '
                'is assigned, plus every group those imply, transitively. A '
                'group the user is not assigned directly is marked "Implied".'))
        else:
            lines.append(_(
                'The three columns show ASSIGNED groups only: the groups ticked '
                'on the user form. Groups that come from an implied group are '
                'not listed - switch Compare to "Effective" to see them.'))
        if not counts['only_a'] and not counts['only_b']:
            lines.append(_(
                'No difference: %(a)s and %(b)s have exactly the same groups.') % {
                    'a': self.user_a_id.display_name,
                    'b': self.user_b_id.display_name})
        else:
            lines.append(_(
                '%(only_a)s group(s) only %(a)s has, %(only_b)s only %(b)s has, '
                '%(shared)s shared.') % {
                    'only_a': counts['only_a'], 'only_b': counts['only_b'],
                    'shared': counts['shared'],
                    'a': self.user_a_id.display_name,
                    'b': self.user_b_id.display_name})
        if copy_count:
            lines.append(_(
                'Copying A to B would ADD %(count)s group(s) to %(b)s and remove '
                'nothing. Only the groups %(a)s is assigned directly are '
                'written; the implied ones follow from them.') % {
                    'count': copy_count, 'a': self.user_a_id.display_name,
                    'b': self.user_b_id.display_name})
        lines.append(_(
            'The model table below is computed on effective groups and on '
            'access control lines only - record rules are not taken into '
            'account.'))
        if truncated:
            lines.append(_(
                'The model table is capped at %s rows per side; the difference '
                'covers more models than that.') % MODEL_LINE_LIMIT)
        return '\n'.join(lines)
