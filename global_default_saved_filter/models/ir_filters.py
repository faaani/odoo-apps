# -*- coding: utf-8 -*-
# Part of global_default_saved_filter. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class IrFilters(models.Model):
    _inherit = 'ir.filters'

    global_default = fields.Boolean(
        string='Default for All Users',
        default=False,
        help='Apply this shared filter by default for every user who has not '
             'chosen a personal default filter. A personal default always '
             'wins over this one.',
    )

    def _unset_sibling_global_defaults(self):
        """Only one global default per (model, action): mirror core's handling
        of personal defaults so flagging a new filter silently demotes the old
        one instead of being ignored because of the id tie-break."""
        for record in self.filtered('global_default'):
            siblings = self.sudo().search([
                ('id', '!=', record.id),
                ('model_id', '=', record.model_id),
                ('action_id', '=', record.action_id.id),
                ('global_default', '=', True),
            ])
            if siblings:
                siblings.write({'global_default': False})

    @api.model_create_multi
    def create(self, vals_list):
        records = super(IrFilters, self).create(vals_list)
        records._unset_sibling_global_defaults()
        return records

    def write(self, vals):
        res = super(IrFilters, self).write(vals)
        if vals.get('global_default'):
            self._unset_sibling_global_defaults()
        return res

    @api.model
    def get_filters(self, model, *args, **kwargs):
        """Mark the shared global-default filter as default for users who have
        no personal default. Core forbids is_default on shared filters at the
        constraint level, so this is resolved at read time instead of stored.

        Signature uses *args/**kwargs: 19.0 added embedded-action parameters.
        """
        res = super(IrFilters, self).get_filters(model, *args, **kwargs)
        try:
            if any(f.get('is_default') for f in res):
                return res  # personal default wins, never override it
            # 19.0 replaced user_id (m2o) with user_ids (m2m); a filter is
            # shared when it targets no specific user in either shape
            shared_ids = [f['id'] for f in res
                          if not f.get('user_id') and not f.get('user_ids')]
            if not shared_ids:
                return res
            candidates = self.sudo().browse(shared_ids).filtered(
                'global_default').sorted('id')
            if candidates:
                target_id = candidates[0].id
                for f in res:
                    if f['id'] == target_id:
                        f['is_default'] = True
                        break
        except Exception:  # noqa: BLE001 — a broken favorite must not break views
            _logger.exception('global_default_saved_filter: get_filters post-processing failed.')
        return res
