# -*- coding: utf-8 -*-
# Part of followers_bulk_manage. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FollowersBulkWizard(models.TransientModel):
    _name = 'followers.bulk.wizard'
    _description = 'Manage Followers in Bulk'

    partner_add_ids = fields.Many2many(
        'res.partner', 'followers_bulk_wizard_add_rel', 'wizard_id', 'partner_id',
        string='Followers to Add')
    partner_remove_ids = fields.Many2many(
        'res.partner', 'followers_bulk_wizard_remove_rel', 'wizard_id', 'partner_id',
        string='Followers to Remove')
    subtype_ids = fields.Many2many(
        'mail.message.subtype', 'followers_bulk_wizard_subtype_rel', 'wizard_id',
        'subtype_id', string='Subscribe To',
        domain="['|', ('res_model', '=', False), ('res_model', '=', res_model)]",
        help='Leave empty to use the default subscription subtypes of the model. '
             'Applies to the followers being added.')
    res_model = fields.Char(string='Model', readonly=True)
    record_count = fields.Integer(string='Records', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super(FollowersBulkWizard, self).default_get(fields_list)
        res.update(res_model=self.env.context.get('active_model'),
                   record_count=len(self._context_record_ids()))
        return res

    def _context_record_ids(self):
        """Selected ids, tolerating the single-record (active_id) binding."""
        ids = self.env.context.get('active_ids') or []
        if not ids and self.env.context.get('active_id'):
            ids = [self.env.context['active_id']]
        return list(ids)

    def _selected_records(self):
        """Resolve the selection and refuse anything we cannot legitimately touch."""
        model = self.env.context.get('active_model')
        ids = self._context_record_ids()
        if not model or not ids:
            raise UserError(_('Select the records whose followers you want to manage first.'))
        records = self.env[model].browse(ids).exists()
        if not records:
            raise UserError(_('The selected records no longer exist.'))
        if 'message_follower_ids' not in records._fields:
            raise UserError(_('Followers cannot be managed on %s.') % model)
        # Changing someone else's subscription is a write on the record: check it
        # up-front so the user gets one clean error instead of a partial run.
        # No sudo() anywhere — the user's own access rights decide.
        if hasattr(records, 'check_access'):
            records.check_access('write')       # 18.0+
        else:
            records.check_access_rights('write')
            records.check_access_rule('write')
        return records

    def _follower_count(self, model, res_ids, partner_ids):
        if not partner_ids:
            return 0
        return self.env['mail.followers'].search_count([
            ('res_model', '=', model),
            ('res_id', 'in', res_ids),
            ('partner_id', 'in', partner_ids),
        ])

    def action_apply(self):
        self.ensure_one()
        add_ids = self.partner_add_ids.ids
        remove_ids = self.partner_remove_ids.ids
        if not add_ids and not remove_ids:
            raise UserError(_('Choose at least one follower to add or to remove.'))
        overlap = self.partner_add_ids & self.partner_remove_ids
        if overlap:
            raise UserError(
                _('%s cannot be added and removed at the same time.')
                % ', '.join(overlap.mapped('display_name')))

        records = self._selected_records()
        model = records._name
        res_ids = records.ids

        removed = 0
        if remove_ids:
            removed = self._follower_count(model, res_ids, remove_ids)
            # KEYWORD arguments only: on 14.0 the second positional of
            # message_(un)subscribe is channel_ids, not subtype_ids.
            records.message_unsubscribe(partner_ids=remove_ids)

        added = 0
        if add_ids:
            before = self._follower_count(model, res_ids, add_ids)
            records.message_subscribe(partner_ids=add_ids,
                                      subtype_ids=self.subtype_ids.ids or None)
            added = self._follower_count(model, res_ids, add_ids) - before

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Followers updated'),
                'message': _(
                    '%(added)s follower(s) added and %(removed)s removed '
                    'across %(records)s record(s).'
                ) % {'added': added, 'removed': removed, 'records': len(records)},
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
