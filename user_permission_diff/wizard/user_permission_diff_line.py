# -*- coding: utf-8 -*-
# Part of user_permission_diff. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

SOURCE_SELECTION = [
    ('assigned', 'Assigned'),
    ('implied', 'Implied'),
    ('none', 'Not a member'),
]


class UserPermissionDiffLine(models.TransientModel):
    _name = 'user.permission.diff.line'
    _description = 'Compared Group'
    _order = 'category_name, group_name, id'

    diff_id = fields.Many2one(
        'user.permission.diff', string='Comparison',
        required=True, ondelete='cascade', index=True)
    group_id = fields.Many2one(
        'res.groups', string='Group', required=True, ondelete='cascade')
    group_name = fields.Char(string='Group Name', required=True)
    category_name = fields.Char(string='Application')
    side = fields.Selection(
        [('only_a', 'Only User A'),
         ('only_b', 'Only User B'),
         ('shared', 'Shared')],
        string='Side', required=True, index=True)
    source_a = fields.Selection(
        SOURCE_SELECTION, string='User A', required=True,
        help='Assigned: the group is ticked on the user form.\n'
             'Implied: the user is a member because another of their groups '
             'implies this one.\n'
             'Not a member: the user does not have this group at all.')
    source_b = fields.Selection(
        SOURCE_SELECTION, string='User B', required=True,
        help='Assigned: the group is ticked on the user form.\n'
             'Implied: the user is a member because another of their groups '
             'implies this one.\n'
             'Not a member: the user does not have this group at all.')
    to_copy = fields.Boolean(
        string='Would Be Copied',
        help='Ticked when a copy from User A to User B would write this very '
             'group on User B. Groups User A only holds through implication '
             'are not written: they follow from the assigned ones.')


class UserPermissionDiffModelLine(models.TransientModel):
    _name = 'user.permission.diff.model.line'
    _description = 'Model Permission Granted by the Difference'
    _order = 'side, model_name, id'

    diff_id = fields.Many2one(
        'user.permission.diff', string='Comparison',
        required=True, ondelete='cascade', index=True)
    side = fields.Selection(
        [('only_a', 'Only User A'), ('only_b', 'Only User B')],
        string='Side', required=True)
    side_label = fields.Char(string='Who')
    model_id = fields.Many2one('ir.model', string='Model', ondelete='cascade')
    model_name = fields.Char(string='Technical Model')
    perm_read = fields.Boolean(string='Read')
    perm_write = fields.Boolean(string='Write')
    perm_create = fields.Boolean(string='Create')
    perm_unlink = fields.Boolean(string='Delete')
    rights_code = fields.Char(
        string='Rights',
        help='Compact form of the four permissions this side has and the other '
             'side has not, for example R-C-.')
