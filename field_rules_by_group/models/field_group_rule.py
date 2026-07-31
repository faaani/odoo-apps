# -*- coding: utf-8 -*-
# Part of field_rules_by_group. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError


class FieldGroupRule(models.Model):
    _name = 'field.group.rule'
    _description = 'Field Rule by Group'
    _order = 'model_name, field_name, id'

    name = fields.Char(string='Rule', compute='_compute_name', store=True)
    model_id = fields.Many2one(
        'ir.model', string='Model', required=True, ondelete='cascade', index=True,
        help='The rule applies to every form view of this model.')
    model_name = fields.Char(
        related='model_id.model', string='Model Name', store=True, readonly=True)
    field_id = fields.Many2one(
        'ir.model.fields', string='Field', required=True, ondelete='cascade',
        domain="[('model_id', '=', model_id)]",
        help='The field to restrict on the selected model.')
    field_name = fields.Char(
        related='field_id.name', string='Field Name', store=True, readonly=True)
    group_ids = fields.Many2many(
        'res.groups', 'field_group_rule_res_groups_rel', 'rule_id', 'group_id',
        string='User Groups',
        help='Users belonging to ANY of these groups are affected. '
             'Leave empty to apply the rule to every user.')
    readonly = fields.Boolean(
        string='Read-Only',
        help='The field cannot be edited on the form, and writes by the '
             'restricted users are also blocked server-side on create and '
             'write. Writes performed by system/sudo flows (for example a '
             'user editing their own preferences) are not blocked.')
    invisible = fields.Boolean(
        string='Invisible',
        help='Hides the field on form views only. The value remains '
             'readable via API calls, exports, list/kanban views and '
             'embedded subviews. It is a UI convenience, not an access '
             'control.')
    required = fields.Boolean(
        string='Required',
        help='The form cannot be saved while the field is empty. '
             'Enforced by the form only, not server-side.')
    apply_to_admin = fields.Boolean(
        string='Apply to System Administrators', default=False,
        help='Off by default: administrators stay exempt so they can always '
             'repair data. Tick to apply this rule to them as well.')
    active = fields.Boolean(default=True)

    @api.depends('model_name', 'field_name', 'readonly', 'invisible', 'required')
    def _compute_name(self):
        # deliberately untranslated: the name is stored, so _() here would
        # freeze the creator's language into every other user's dialogs
        labels = (('readonly', 'read-only'),
                  ('invisible', 'invisible'),
                  ('required', 'required'))
        for rule in self:
            flags = [label for flag, label in labels if rule[flag]]
            if rule.model_name and rule.field_name:
                rule.name = '%s.%s: %s' % (
                    rule.model_name, rule.field_name, ' + '.join(flags))
            else:
                rule.name = 'New Field Rule'

    # field_id is in the list so the check also fires on a create() that
    # passes none of the three flags at all
    @api.constrains('field_id', 'readonly', 'invisible', 'required')
    def _check_flags(self):
        for rule in self:
            if not (rule.readonly or rule.invisible or rule.required):
                raise ValidationError(_(
                    'A field rule must set at least one of Read-Only, '
                    'Invisible or Required.'))
            if rule.invisible and rule.required:
                raise ValidationError(_(
                    'A rule cannot make a field both invisible and required: '
                    'the form could never be saved.'))

    @api.constrains('model_id', 'field_id')
    def _check_field_model(self):
        # the view domain cannot stop RPC/CSV writes from pairing a field
        # with a foreign model; such a rule would then match by field NAME
        # on the wrong model
        for rule in self:
            if rule.field_id and rule.model_id \
                    and rule.field_id.model_id != rule.model_id:
                raise ValidationError(_(
                    'The field "%(field)s" does not belong to the model '
                    '"%(model)s".'
                ) % {'field': rule.field_id.name,
                     'model': rule.model_id.model})

    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.field_id = False

    @api.model
    @tools.ormcache('model_name')
    def _get_rules(self, model_name):
        """Active rules for one model, as a tuple of plain dicts (recordsets
        must never live inside an ormcache). One cached dict lookup is all a
        model without rules ever costs.

        sudo() here only READS the administrator's rule configuration in
        order to APPLY restrictions to the current user: it tightens access
        and never widens it. Regular users still have no read access to the
        rule records themselves (see ir.model.access.csv).
        """
        rules = self.sudo().search(
            [('model_name', '=', model_name), ('active', '=', True)])
        return tuple({
            'id': rule.id,
            'name': rule.name,
            'field': rule.field_name,
            'groups': tuple(rule.group_ids.ids),
            'readonly': rule.readonly,
            'invisible': rule.invisible,
            'required': rule.required,
            'apply_to_admin': rule.apply_to_admin,
        } for rule in rules)

    def _clear_rules_cache(self):
        registry = self.env.registry
        if hasattr(registry, 'clear_cache'):
            registry.clear_cache()      # 17.0+
        else:
            registry.clear_caches()     # up to 16.0

    @api.model_create_multi
    def create(self, vals_list):
        rules = super(FieldGroupRule, self).create(vals_list)
        self._clear_rules_cache()
        return rules

    def write(self, vals):
        res = super(FieldGroupRule, self).write(vals)
        self._clear_rules_cache()
        return res

    def unlink(self):
        res = super(FieldGroupRule, self).unlink()
        self._clear_rules_cache()
        return res
