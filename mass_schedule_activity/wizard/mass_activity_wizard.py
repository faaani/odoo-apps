# -*- coding: utf-8 -*-
# Part of mass_schedule_activity. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MassActivityWizard(models.TransientModel):
    _name = 'mass.activity.wizard'
    _description = 'Schedule Activities in Bulk'

    activity_type_id = fields.Many2one(
        'mail.activity.type', string='Activity Type', required=True,
        # 14.0 scopes activity types with res_model_id (m2o to ir.model);
        # the res_model Selection only exists from 15.0 on
        domain="['|', ('res_model_id', '=', False), ('res_model_id.model', '=', res_model)]")
    summary = fields.Char(string='Summary')
    note = fields.Html(string='Note')
    date_deadline = fields.Date(
        string='Due Date', required=True, default=fields.Date.context_today)
    user_id = fields.Many2one(
        'res.users', string='Assigned To', required=True,
        default=lambda self: self.env.user)
    res_model = fields.Char(string='Model', readonly=True)
    record_count = fields.Integer(string='Records', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super(MassActivityWizard, self).default_get(fields_list)
        model = self.env.context.get('active_model')
        ids = self.env.context.get('active_ids') or []
        if self.env.context.get('active_id') and not ids:
            ids = [self.env.context['active_id']]
        res.update(res_model=model, record_count=len(ids))
        return res

    def action_schedule(self):
        self.ensure_one()
        model = self.env.context.get('active_model')
        ids = self.env.context.get('active_ids') or []
        if not model or not ids:
            raise UserError(_('Select the records to schedule an activity on first.'))
        records = self.env[model].browse(ids).exists()
        if not records:
            raise UserError(_('The selected records no longer exist.'))
        if not hasattr(records, 'activity_schedule'):
            raise UserError(_('Activities cannot be scheduled on %s.') % model)
        # activity_schedule() applies the model's own access rules per record,
        # so a user can never create activities on records they cannot see
        records.activity_schedule(
            act_type_xmlid=False,
            date_deadline=self.date_deadline,
            summary=self.summary or '',
            note=self.note or False,
            activity_type_id=self.activity_type_id.id,
            user_id=self.user_id.id,
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Activities scheduled'),
                'message': _('%(count)s activity(ies) created for %(user)s.') % {
                    'count': len(records), 'user': self.user_id.display_name},
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
