# -*- coding: utf-8 -*-
# Part of user_permission_diff. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.mail import plaintext2html

from .user_permission_diff import (
    check_actor, check_target, groups_to_grant, user_groups_field,
)


class UserPermissionDiffCopy(models.TransientModel):
    _name = 'user.permission.diff.copy'
    _description = 'Confirm Copying Groups Between Users'

    diff_id = fields.Many2one(
        'user.permission.diff', string='Comparison', ondelete='cascade')
    source_user_id = fields.Many2one(
        'res.users', string='Copy From', required=True, ondelete='cascade',
        readonly=True)
    target_user_id = fields.Many2one(
        'res.users', string='Copy To', required=True, ondelete='cascade',
        readonly=True)
    group_ids = fields.Many2many(
        'res.groups', string='Groups To Grant', readonly=True,
        help='The groups that will be added to the target user. This list is '
             'recomputed from the two users when Grant is pressed.')
    group_count = fields.Integer(
        string='Groups', compute='_compute_group_count')
    confirmed = fields.Boolean(
        string='I have read the list and want to grant these groups',
        help='The server refuses to grant anything while this box is unticked.')
    warning = fields.Text(string='What Will Happen', compute='_compute_warning')

    @api.depends('group_ids')
    def _compute_group_count(self):
        for wizard in self:
            wizard.group_count = len(wizard.group_ids)

    @api.depends('group_ids', 'source_user_id', 'target_user_id')
    def _compute_warning(self):
        for wizard in self:
            wizard.warning = '\n'.join([
                _('%(count)s group(s) will be ADDED to %(target)s.') % {
                    'count': len(wizard.group_ids),
                    'target': wizard.target_user_id.display_name},
                _('No group is ever removed: %(target)s keeps every group they '
                  'already have.') % {
                    'target': wizard.target_user_id.display_name},
                _('This grants access rights. The change is written in the '
                  'chatter of %(target)s and cannot be undone from here - to '
                  'reverse it, untick the groups on the user form.') % {
                    'target': wizard.target_user_id.display_name},
            ])

    @api.model
    def _log_thread(self, user):
        """Where the grant is logged.

        res.users is not itself a mail thread on every supported series; its
        partner is, and that is the chatter shown on the user's contact.
        """
        return user if hasattr(user, 'message_post') else user.partner_id

    def action_apply(self):
        self.ensure_one()
        # Re-checked here, not only when the dialog was opened: this is the
        # method that writes, and it can be called directly over RPC.
        check_actor(self.env)
        target = self.target_user_id
        check_target(self.env, target)
        if not self.confirmed:
            raise UserError(_(
                'Tick "I have read the list and want to grant these groups" '
                'before granting anything.'))

        # The list carried by the dialog is display only: what is granted is
        # recomputed from the two users, so a forged payload changes nothing.
        groups = groups_to_grant(self.env, self.source_user_id, target)
        if not groups:
            raise UserError(_(
                '%(target)s already has every group %(source)s is assigned: '
                'there is nothing to copy.') % {
                    'target': target.display_name,
                    'source': self.source_user_id.display_name})

        field = user_groups_field(self.env)
        before = set(target[field].ids)
        try:
            # link commands only - never (6, 0, ids), which would replace the
            # target's groups and silently remove the ones A does not have
            target.write({field: [(4, group_id) for group_id in groups.ids]})
        except ValidationError as err:
            raise UserError(_(
                'Odoo refused the change and nothing was granted: %(error)s\n'
                'This usually means the two users are not of the same type '
                '(internal, portal or public), which Odoo does not allow to '
                'mix.') % {'error': err.args[0] if err.args else err}) from err
        after = set(target[field].ids)
        removed = before - after
        if removed:
            # Defensive: a copy must only ever add. Raising undoes the write.
            raise UserError(_(
                'The write would have removed %s group(s) from the target user, '
                'which this module never does. Nothing was changed.'
            ) % len(removed))

        self._log_grant(target, groups)
        if self.diff_id:
            self.diff_id._build_lines()
            self.diff_id.notice = _(
                'Granted %(count)s group(s) to %(target)s, copied from '
                '%(source)s. Nothing was removed.\n') % {
                    'count': len(groups), 'target': target.display_name,
                    'source': self.source_user_id.display_name,
            } + (self.diff_id.notice or '')
            return self.diff_id._reopen()
        return {'type': 'ir.actions.act_window_close'}

    def _log_grant(self, target, groups):
        """Write what was granted in the chatter of the target user."""
        body = plaintext2html('\n'.join([
            _('%(count)s group(s) granted, copied from %(source)s by '
              '%(actor)s:') % {
                'count': len(groups),
                'source': self.source_user_id.display_name,
                'actor': self.env.user.display_name},
            '\n'.join('- %s' % group.display_name for group in groups),
            _('No group was removed.'),
        ]))
        self._log_thread(target).message_post(
            body=Markup(body),
            subject=_('Permissions copied from %s') % self.source_user_id.display_name,
        )
