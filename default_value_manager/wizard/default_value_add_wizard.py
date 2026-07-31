# -*- coding: utf-8 -*-
# Part of default_value_manager. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Field types a value can be typed in for. x2many, binary and reference
# defaults exist and are listed by the screen, but they cannot be expressed as
# a single typed value, so they are not offered here. Stated on the store page.
SUPPORTED_TTYPES = [
    'char', 'text', 'html', 'boolean', 'integer', 'float',
    'monetary', 'date', 'datetime', 'selection', 'many2one',
]
# Candidates listed back to the user when a many2one value is ambiguous.
MANY2ONE_SUGGESTIONS = 5


class DefaultValueAddWizard(models.TransientModel):
    _name = 'default.value.add.wizard'
    _description = 'Set a Default Value'

    model_id = fields.Many2one(
        'ir.model', string='Model', required=True, ondelete='cascade',
        domain=[('transient', '=', False)],
        help='The model whose field should be pre-filled.',
    )
    field_id = fields.Many2one(
        'ir.model.fields', string='Field', required=True, ondelete='cascade',
        help='The field to pre-fill. Only stored, writable fields of a type a '
             'value can be typed in for are listed.',
    )
    field_ttype = fields.Selection(
        related='field_id.ttype', string='Field Type', readonly=True)
    field_relation = fields.Char(
        related='field_id.relation', string='Target Model', readonly=True)
    value_text = fields.Char(
        string='Value',
        help='The value to pre-fill. For a many2one, type the name of the '
             'target record or its database id. For a selection, type the '
             'label or the stored key.',
    )
    value_boolean = fields.Boolean(
        string='Ticked',
        help='The value a boolean field is pre-filled with.',
    )
    value_hint = fields.Char(
        string='Expected Value', compute='_compute_value_hint',
        help='What this field accepts as a default value.',
    )
    scope_user = fields.Selection(
        [('all', 'All users'), ('user', 'One user')],
        string='Applies To', required=True, default='all',
        help='"All users" writes a default everybody gets; "One user" writes a '
             'personal default for the user you pick.',
    )
    user_id = fields.Many2one(
        'res.users', string='User', ondelete='cascade',
        help='The only user this default will apply to.',
    )
    scope_company = fields.Selection(
        [('all', 'All companies'), ('company', 'One company')],
        string='Company Scope', required=True, default='all',
        help='"All companies" writes a default valid in every company; '
             '"One company" restricts it to the company you pick.',
    )
    company_id = fields.Many2one(
        'res.company', string='Company', ondelete='cascade',
        help='The only company this default will apply to.',
    )
    condition = fields.Char(
        string='Condition',
        help='Optional, advanced: restricts the default to a context of the '
             'form "other_field=value", exactly as Odoo stores it. Leave empty '
             'for a default that always applies.',
    )
    existing_warning = fields.Char(
        string='Existing Entry', compute='_compute_existing_warning',
        help='Set when a default already exists for the same field and the same '
             'scope: writing this one replaces it.',
    )

    @api.depends('field_id')
    def _compute_value_hint(self):
        hints = {
            'boolean': _('Use the "Ticked" checkbox below.'),
            'integer': _('A whole number, e.g. 3.'),
            'float': _('A number, e.g. 12.5 (use a dot as decimal separator).'),
            'monetary': _('An amount, e.g. 12.5 (use a dot as decimal separator).'),
            'date': _('A date as YYYY-MM-DD, e.g. 2024-12-31.'),
            'datetime': _('A date and time in UTC as YYYY-MM-DD HH:MM:SS.'),
        }
        for wizard in self:
            field = wizard._registry_field()
            if field is None:
                wizard.value_hint = False
            elif field.type == 'selection':
                labels = self.env['default.value.entry']._selection_labels(
                    wizard.field_id.model, wizard.field_id.name)
                if labels:
                    wizard.value_hint = _('One of: %s', ', '.join(
                        '%s (%s)' % (label, key) for key, label in labels.items() if key))
                else:
                    wizard.value_hint = _('One of the values this selection accepts.')
            elif field.type == 'many2one':
                wizard.value_hint = _('The name or the database id of a %s record.',
                                      field.comodel_name)
            else:
                wizard.value_hint = hints.get(field.type, _('Free text.'))

    @api.depends('field_id', 'scope_user', 'user_id', 'scope_company', 'company_id', 'condition')
    def _compute_existing_warning(self):
        for wizard in self:
            wizard.existing_warning = False
            if not wizard.field_id:
                continue
            existing = self.env['ir.default'].search([
                ('field_id', '=', wizard.field_id.id),
                ('user_id', '=', wizard._target_user_id()),
                ('company_id', '=', wizard._target_company_id()),
                ('condition', '=', wizard.condition or False),
            ], limit=1)
            if existing:
                # same id, so the entry screen renders the current value readably
                current = self.env['default.value.entry'].browse(existing.id)
                wizard.existing_warning = _(
                    'A default already exists for this field and this scope '
                    '(current value: %s). Saving replaces it.',
                    current.value_display or existing.json_value)

    @api.onchange('model_id')
    def _onchange_model_id(self):
        if self.field_id and self.field_id.model_id != self.model_id:
            self.update({'field_id': False})

    @api.onchange('scope_user')
    def _onchange_scope_user(self):
        if self.scope_user == 'all':
            self.update({'user_id': False})

    @api.onchange('scope_company')
    def _onchange_scope_company(self):
        if self.scope_company == 'all':
            self.update({'company_id': False})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _registry_field(self):
        """The registry field behind ``field_id``, or None when it is not one.

        ir.model.fields can hold rows for models or fields that are no longer
        installed; those cannot be given a default value.
        """
        self.ensure_one()
        model_name = self.field_id.model
        if not model_name or model_name not in self.env:
            return None
        return self.env[model_name]._fields.get(self.field_id.name)

    def _target_user_id(self):
        self.ensure_one()
        return self.user_id.id if self.scope_user == 'user' else False

    def _target_company_id(self):
        self.ensure_one()
        return self.company_id.id if self.scope_company == 'company' else False

    def _coerce_selection(self, field, text):
        labels = self.env['default.value.entry']._selection_labels(
            self.field_id.model, self.field_id.name)
        if text in labels:
            return text
        for key, label in labels.items():
            if label and label.strip().lower() == text.lower():
                return key
        raise UserError(_(
            'The value "%(value)s" is not one of the values %(field)s accepts.\n'
            'Accepted values: %(accepted)s',
            value=text, field=self.field_id.name,
            accepted=', '.join('%s (%s)' % (label, key)
                               for key, label in labels.items() if key) or _('none')))

    def _coerce_many2one(self, field, text):
        comodel = field.comodel_name
        if comodel not in self.env:
            raise UserError(_('The target model %s is not installed.', comodel))
        target = self.env[comodel].with_context(active_test=False)
        if text.isdigit():
            record = target.browse(int(text)).exists()
            if not record:
                raise UserError(_('There is no %(model)s record with id %(id)s.',
                                  model=comodel, id=text))
            return record.id
        matches = target.name_search(text, operator='=', limit=MANY2ONE_SUGGESTIONS + 1)
        if not matches:
            matches = target.name_search(text, operator='ilike', limit=MANY2ONE_SUGGESTIONS + 1)
        if not matches:
            raise UserError(_(
                'No %(model)s record is named "%(value)s". Type an exact name, '
                'or the database id of the record.', model=comodel, value=text))
        if len(matches) > 1:
            raise UserError(_(
                'Several %(model)s records match "%(value)s": %(candidates)s.\n'
                'Type the exact name, or the database id of the one you want.',
                model=comodel, value=text,
                candidates=', '.join(name for _id, name in matches[:MANY2ONE_SUGGESTIONS])))
        return matches[0][0]

    def _coerce_value(self, field):
        """The typed value to hand over to ir.default.set()."""
        self.ensure_one()
        ttype = field.type
        if ttype == 'boolean':
            return self.value_boolean
        text = (self.value_text or '').strip()
        if not text:
            raise UserError(_('Type the value the field should be pre-filled with.'))
        if ttype in ('char', 'text', 'html'):
            return text
        if ttype == 'integer':
            try:
                return int(text)
            except ValueError:
                raise UserError(_('"%s" is not a whole number.', text))
        if ttype in ('float', 'monetary'):
            try:
                return float(text)
            except ValueError:
                raise UserError(_('"%s" is not a number. Use a dot as decimal separator.', text))
        if ttype == 'date':
            try:
                return fields.Date.to_string(fields.Date.to_date(text))
            except (ValueError, TypeError):
                raise UserError(_('"%s" is not a date. Use the YYYY-MM-DD format.', text))
        if ttype == 'datetime':
            try:
                return fields.Datetime.to_string(fields.Datetime.to_datetime(text))
            except (ValueError, TypeError):
                raise UserError(_(
                    '"%s" is not a date and time. Use the YYYY-MM-DD HH:MM:SS format (UTC).',
                    text))
        if ttype == 'selection':
            return self._coerce_selection(field, text)
        if ttype == 'many2one':
            return self._coerce_many2one(field, text)
        raise UserError(_(
            'A default value cannot be typed in for a %s field from this screen.', ttype))

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------
    def action_set_default(self):
        self.ensure_one()
        if self.field_id.model_id != self.model_id:
            raise UserError(_('The field %(field)s does not belong to the model %(model)s.',
                              field=self.field_id.name, model=self.model_id.model))
        field = self._registry_field()
        if field is None:
            raise UserError(_(
                'The field %(field)s no longer exists on %(model)s in this '
                'database, so no default can be set on it.',
                field=self.field_id.name, model=self.field_id.model))
        if self.scope_user == 'user' and not self.user_id:
            raise UserError(_('Pick the user this default applies to.'))
        if self.scope_company == 'company' and not self.company_id:
            raise UserError(_('Pick the company this default applies to.'))
        value = self._coerce_value(field)
        # ir.default.set() is the supported entry point: it re-validates the
        # value against the field, replaces an existing entry for the same
        # scope, checks access rights on the field and clears the cache.
        self.env['ir.default'].set(
            self.field_id.model, self.field_id.name, value,
            user_id=self._target_user_id(),
            company_id=self._target_company_id(),
            condition=self.condition or False,
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Default value set'),
                'message': _('%(model)s / %(field)s will now be pre-filled.',
                             model=self.model_id.name, field=self.field_id.field_description),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
