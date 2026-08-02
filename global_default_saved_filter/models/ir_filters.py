# -*- coding: utf-8 -*-
# Part of global_default_saved_filter. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class IrFilters(models.Model):
    _inherit = 'ir.filters'

    global_default = fields.Boolean(
        string='Default for All Users',
        default=False,
        help='Apply this shared filter by default for every user who has not '
             'chosen a personal default filter. A personal default always '
             'wins over this one. Only a shared filter can carry the flag, '
             'and only administrators (Access Rights) may change it.',
    )

    def _check_global_default_manager(self):
        """Changing a company-wide default is an administrative act: setting it
        silently demotes the previous global default for the same model/action
        (see _unset_sibling_global_defaults) and clearing it removes the
        default for everyone. Core grants even portal/public users CRUD on
        their own ir.filters, so without this gate any user could hijack or
        drop the administrator's default."""
        if self.env.su or self.env.user.has_group('base.group_erp_manager'):
            return
        raise AccessError(_(
            'Only administrators with access-rights management privileges '
            'may change the default filter for all users.'))

    def _global_default_shared_domain(self):
        """A filter is shared when it targets no specific user. 19.0 replaced
        user_id (m2o) with user_ids (m2m)."""
        if 'user_ids' in self._fields:
            return [('user_ids', '=', False)]
        return [('user_id', '=', False)]

    def _check_global_default_shared(self):
        """global_default only means something on a SHARED filter: get_filters
        never surfaces a personal filter to anybody else, so allowing the flag
        on an owned filter would demote the real company-wide default in
        exchange for nothing."""
        for record in self:
            owner = record.user_ids if 'user_ids' in self._fields else record.user_id
            if owner:
                raise ValidationError(_(
                    'Only a shared filter (one that belongs to no specific '
                    'user) can be made the default for all users.'))

    def _unset_sibling_global_defaults(self):
        """Only one global default per (model, action): mirror core's handling
        of personal defaults so flagging a new filter silently demotes the old
        one instead of being ignored because of the id tie-break.

        INVARIANT: this method writes other users' filters under sudo(), which
        is safe ONLY because every caller has already passed
        _check_global_default_manager() on the *stored* value (not on the
        caller-supplied vals, which a context default can bypass) — the actor
        is a vetted ERP manager, so demoting siblings is a privileged,
        deliberate act. The search is scoped to shared filters for the same
        action so a personal filter can never demote the company default."""
        for record in self.filtered('global_default'):
            domain = [
                ('id', '!=', record.id),
                ('model_id', '=', record.model_id),
                ('action_id', '=', record.action_id.id),
                ('global_default', '=', True),
            ] + self._global_default_shared_domain()
            # 18.0/19.0 made the embedded action part of a filter's identity
            if 'embedded_action_id' in self._fields:
                domain.append(
                    ('embedded_action_id', '=', record.embedded_action_id.id))
            if 'embedded_parent_res_id' in self._fields:
                domain.append(
                    ('embedded_parent_res_id', '=', record.embedded_parent_res_id))
            siblings = self.sudo().search(domain)
            if siblings:
                siblings.write({'global_default': False})

    @api.model_create_multi
    def create(self, vals_list):
        records = super(IrFilters, self).create(vals_list)
        # Check the STORED value, never the incoming vals: default_global_default
        # in the context (or an ir.default) sets the field without ever
        # appearing in vals_list, which would bypass a vals-based guard.
        flagged = records.filtered('global_default')
        if flagged:
            self._check_global_default_manager()
            flagged._check_global_default_shared()
        records._unset_sibling_global_defaults()
        return records

    def write(self, vals):
        if 'global_default' in vals:
            target = bool(vals['global_default'])
            # guard BOTH directions: clearing the flag drops everyone's default
            if any(record.global_default != target for record in self):
                self._check_global_default_manager()
        res = super(IrFilters, self).write(vals)
        if vals.get('global_default'):
            self.filtered('global_default')._check_global_default_shared()
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
