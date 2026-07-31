# -*- coding: utf-8 -*-
# Part of mass_field_update. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import json
import logging

import psycopg2

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# One run never touches more than this many records: past that the job belongs
# to an import or a scheduled action, not to a dialog the user waits on.
MAX_RECORDS = 10000

# How many record names are quoted per reason in the result report.
MAX_REPORTED = 20

# Field types the wizard knows how to render an input for AND write back.
SUPPORTED_TYPES = (
    'char', 'text', 'html', 'integer', 'float', 'monetary',
    'boolean', 'date', 'datetime', 'selection', 'many2one',
)

# Bookkeeping columns, plus the archive flag on purpose: archiving/unarchiving
# has its own dedicated (and reversible) tools, and cascades to related records.
BLOCKED_FIELD_NAMES = frozenset({
    'id', 'create_uid', 'create_date', 'write_uid', 'write_date',
    '__last_update', 'display_name', 'active', 'active_test',
})

# A field whose name contains any of these is treated as a credential and is
# never offered - mass-writing one would lock people out or hand out access.
CREDENTIAL_MARKERS = ('password', 'passwd', 'secret', 'token', 'api_key', 'apikey')

# Bound to the calling context at creation time, never rewritable afterwards.
PINNED_FIELDS = ('res_model', 'model_label', 'record_ids_json', 'selected_count')

# Credential-ish fields whose name carries no marker.
CREDENTIAL_FIELDS = frozenset({
    ('res.users', 'login'),
    ('res.users', 'oauth_uid'),
    ('res.users', 'oauth_provider_id'),
})


class MassFieldUpdateWizard(models.TransientModel):
    _name = 'mass.field.update.wizard'
    _description = 'Update a Field on Many Records'

    state = fields.Selection(
        [('choose', 'Choose'), ('confirm', 'Confirm'), ('done', 'Result')],
        string='Step', default='choose', required=True)

    # --- what was selected -------------------------------------------------
    res_model = fields.Char(string='Model', readonly=True)
    model_label = fields.Char(string='Model Name', readonly=True)
    record_ids_json = fields.Text(string='Selected Records', readonly=True)
    selected_count = fields.Integer(string='Selected', readonly=True)
    too_many = fields.Boolean(string='Too Many', compute='_compute_too_many')

    # --- the field ---------------------------------------------------------
    field_id = fields.Many2one(
        'ir.model.fields', string='Field to Update', ondelete='cascade',
        domain="[('id', 'in', available_field_ids)]",
        help='Only fields you are allowed to write on this model are listed.')
    available_field_ids = fields.Many2many(
        'ir.model.fields', string='Available Fields',
        compute='_compute_available_field_ids')
    field_name = fields.Char(string='Technical Name', compute='_compute_field_meta')
    field_label = fields.Char(string='Field', compute='_compute_field_meta')
    field_type = fields.Char(string='Type', compute='_compute_field_meta')
    input_widget = fields.Selection(
        [('char', 'Text'), ('text', 'Multi-line text'), ('html', 'HTML'),
         ('integer', 'Integer'), ('float', 'Decimal'), ('boolean', 'Checkbox'),
         ('date', 'Date'), ('datetime', 'Date & Time'), ('selection', 'Selection'),
         ('selection_free', 'Selection (typed)'), ('reference', 'Record')],
        string='Input', compute='_compute_field_meta')
    comodel_id = fields.Many2one(
        'ir.model', string='Related Model', compute='_compute_field_meta')
    value_hint = fields.Char(string='Allowed Values', compute='_compute_field_meta')

    # --- the value ---------------------------------------------------------
    clear_value = fields.Boolean(
        string='Clear the value',
        help='Empty the field instead of writing a value. Required fields are refused.')
    # One input per type: the view shows the one matching the chosen field.
    # The labels differ on purpose (Odoo warns about duplicates); the form
    # overrides them all with a plain "New value".
    value_char = fields.Char(string='New Value')
    value_text = fields.Text(string='New Value (text)')
    value_html = fields.Html(string='New Value (HTML)')
    value_integer = fields.Integer(string='New Value (integer)')
    value_float = fields.Float(string='New Value (number)', digits=(16, 6))
    value_boolean = fields.Boolean(string='New Value (checkbox)')
    value_date = fields.Date(string='New Value (date)')
    value_datetime = fields.Datetime(string='New Value (date & time)')
    value_selection_id = fields.Many2one(
        'ir.model.fields.selection', string='New Value (selection)',
        domain="[('field_id', '=', field_id)]", ondelete='cascade')
    value_selection_free = fields.Char(string='New Value (selection key)')
    value_reference = fields.Reference(
        selection='_selection_reference_models', string='New Value (record)')
    value_display = fields.Char(string='Value', compute='_compute_value_display')

    log_note = fields.Boolean(
        string='Log a note in the chatter', default=True,
        help='Log a note on every changed record, on the models that have a chatter.')

    # --- preview / result --------------------------------------------------
    match_count = fields.Integer(string='Will Change', compute='_compute_preview')
    unchanged_count = fields.Integer(string='Already Set', compute='_compute_preview')
    hidden_count = fields.Integer(string='Not Visible', compute='_compute_preview')
    missing_count = fields.Integer(string='Deleted', compute='_compute_preview')
    preview_count = fields.Integer(string='Announced', readonly=True)
    updated_count = fields.Integer(string='Updated', readonly=True)
    skipped_count = fields.Integer(string='Skipped', readonly=True)
    failed_count = fields.Integer(string='Failed', readonly=True)
    result_details = fields.Text(string='Details', readonly=True)

    # ------------------------------------------------------------------
    # Context plumbing
    # ------------------------------------------------------------------
    @api.model
    def _selection_reference_models(self):
        # Metadata only: model names, never user records. sudo() because
        # ir.model is not readable by everyone, exactly like the standard
        # "Update a Record" server action does for its own Reference field.
        return [(model.model, model.name)
                for model in self.env['ir.model'].sudo().search([])]

    @api.model
    def _context_record_ids(self):
        ids = list(self.env.context.get('active_ids') or [])
        if not ids and self.env.context.get('active_id'):
            ids = [self.env.context['active_id']]
        # type() and not isinstance(): booleans are integers in Python, and a
        # forged [true, false] must not become the records 1 and 0
        seen, clean = set(), []
        for rid in ids:
            if type(rid) is int and rid not in seen:
                seen.add(rid)
                clean.append(rid)
        return clean

    @api.model
    def default_get(self, fields_list):
        res = super(MassFieldUpdateWizard, self).default_get(fields_list)
        model_name = self.env.context.get('active_model')
        if model_name and model_name in self.env.registry:
            ids = self._context_record_ids()
            res.update(
                res_model=model_name,
                model_label=self.env[model_name]._description or model_name,
                record_ids_json=json.dumps(ids),
                selected_count=len(ids),
            )
        return res

    @api.model_create_multi
    def create(self, vals_list):
        # The selection comes from the calling context, never from the client
        # payload: readonly= is a UI flag only, so these values can be forged.
        model_name = self.env.context.get('active_model')
        if model_name and model_name in self.env.registry:
            ids = self._context_record_ids()
            for vals in vals_list:
                vals['res_model'] = model_name
                vals['model_label'] = self.env[model_name]._description or model_name
                vals['record_ids_json'] = json.dumps(ids)
                vals['selected_count'] = len(ids)
        return super(MassFieldUpdateWizard, self).create(vals_list)

    def write(self, vals):
        # The model and the selection are stamped once, at creation, from the
        # calling context. A later RPC call may not re-point a wizard that has
        # already been previewed at another model or at other records.
        if any(key in vals for key in PINNED_FIELDS) and any(self.mapped('res_model')):
            vals = {key: value for key, value in vals.items() if key not in PINNED_FIELDS}
        return super(MassFieldUpdateWizard, self).write(vals)

    def _target_model_name(self):
        self.ensure_one()
        # the value stored at creation wins: the context of a later button call
        # is as forgeable as the record's own fields
        model_name = self.res_model or self.env.context.get('active_model')
        if not model_name or model_name not in self.env.registry:
            raise UserError(_('Open this action from the list of records you want to update.'))
        return model_name

    def _record_ids(self):
        self.ensure_one()
        try:
            ids = json.loads(self.record_ids_json or '[]')
        except (TypeError, ValueError):
            ids = []
        return [rid for rid in ids if type(rid) is int]

    # ------------------------------------------------------------------
    # Which fields may be offered
    # ------------------------------------------------------------------
    def _user_in_field_groups(self, groups_spec):
        try:
            user = self.env.user
            if hasattr(user, 'has_groups'):          # 18.0+
                return user.has_groups(groups_spec)
            return self.user_has_groups(groups_spec)  # 14.0 - 17.0
        except Exception:                             # noqa: BLE001 - unknown xmlid
            return False

    @api.model
    def _record_readable(self, record):
        """Whether this user may read that one record, rules included.

        The ORM cache is shared by every environment of the transaction, so
        touching a field is not a reliable access test: ask explicitly.
        """
        if hasattr(record, 'has_access'):                          # 18.0+
            return record.has_access('read')
        if not record.check_access_rights('read', raise_exception=False):
            return False
        try:
            record.check_access_rule('read')                       # 14.0 - 17.0
        except AccessError:
            return False
        return True

    @api.model
    def _model_writable(self, model):
        if hasattr(model, 'has_access'):              # 18.0+
            return model.browse().has_access('write')
        return model.check_access_rights('write', raise_exception=False)

    @api.model
    def _field_refusal(self, model_name, field_name):
        """Return None when the field may be mass-updated, else why it may not.

        This is the single gate: it feeds the dropdown *and* runs again at apply
        time, so a field name forged over RPC is refused just the same.
        """
        if not model_name or model_name not in self.env.registry:
            return _('Unknown model.')
        model = self.env[model_name]
        field = model._fields.get(field_name)
        if field is None:
            return _('"%(name)s" is not a field of %(model)s.',
                     name=field_name, model=model_name)
        if field_name in BLOCKED_FIELD_NAMES:
            if field_name == 'active':
                return _('Archiving is not done here - use Archive/Unarchive.')
            return _('Technical field maintained by Odoo.')
        lowered = field_name.lower()
        if (model_name, field_name) in CREDENTIAL_FIELDS \
                or any(marker in lowered for marker in CREDENTIAL_MARKERS):
            return _('Credential fields are never mass-updated.')
        if field.type not in SUPPORTED_TYPES:
            return _('Fields of type "%s" are not supported.', field.type)
        # A related (or delegated) field writes on the record at the far end of
        # the relation, which may be shared by several of the selected records:
        # what would be counted and what would be written would not match.
        if getattr(field, 'related', False):
            return _('Related field - update it on the model that owns it.')
        if field.readonly:
            return _('Read-only field.')
        # A stored compute declared readonly=False is what Odoo itself lets you
        # edit in the form (Salesperson, and friends): writing it is legitimate.
        # A compute that is not stored can only be written through an inverse,
        # and could not be counted with a domain either.
        if not field.store:
            return _('Field is not stored in the database.')
        if getattr(field, 'company_dependent', False):
            return _('Company-dependent field.')
        if getattr(field, 'automatic', False):
            return _('Technical field maintained by Odoo.')
        if field.groups and not self._user_in_field_groups(field.groups):
            return _('You do not have access to this field.')
        return None

    @api.model
    def _updatable_field_names(self, model_name):
        if not model_name or model_name not in self.env.registry:
            return []
        model = self.env[model_name]
        if not self._model_writable(model):
            return []
        return [name for name in model._fields
                if not self._field_refusal(model_name, name)]

    @api.depends('res_model')
    def _compute_available_field_ids(self):
        Fields = self.env['ir.model.fields']
        for wizard in self:
            names = wizard._updatable_field_names(wizard.res_model)
            wizard.available_field_ids = Fields.search([
                ('model', '=', wizard.res_model), ('name', 'in', names),
            ]) if names else Fields.browse()

    @api.depends('selected_count')
    def _compute_too_many(self):
        for wizard in self:
            wizard.too_many = wizard.selected_count > MAX_RECORDS

    # ------------------------------------------------------------------
    # The chosen field
    # ------------------------------------------------------------------
    def _safe_field(self):
        """The odoo Field behind field_id, or None when it cannot be used."""
        self.ensure_one()
        model_name = self.res_model or self.env.context.get('active_model')
        name = self.field_id.name
        if not model_name or not name or model_name not in self.env.registry:
            return None
        if self.field_id.model != model_name:
            return None
        if self._field_refusal(model_name, name):
            return None
        return self.env[model_name]._fields[name]

    def _target_field(self):
        """Re-validate the field at apply time and return it, or raise."""
        self.ensure_one()
        model_name = self._target_model_name()
        if not self.field_id:
            raise UserError(_('Choose the field to update.'))
        if self.field_id.model != model_name:
            raise UserError(
                _('"%(field)s" belongs to %(other)s, not to %(model)s.',
                  field=self.field_id.name, other=self.field_id.model, model=model_name))
        refusal = self._field_refusal(model_name, self.field_id.name)
        if refusal:
            raise UserError(_('"%(field)s" cannot be mass-updated: %(reason)s',
                              field=self.field_id.name, reason=refusal))
        return self.env[model_name]._fields[self.field_id.name]

    def _field_selection(self, field):
        """Live [(value, label)] of a selection field, callable ones included."""
        self.ensure_one()
        description = self.env[field.model_name].fields_get([field.name])
        return description.get(field.name, {}).get('selection') or []

    @api.depends('field_id', 'res_model')
    def _compute_field_meta(self):
        Model = self.env['ir.model']
        for wizard in self:
            field = wizard._safe_field()
            wizard.field_name = field.name if field else False
            wizard.field_label = field.string if field else False
            wizard.field_type = field.type if field else False
            wizard.comodel_id = Model.browse()
            wizard.value_hint = False
            if not field:
                wizard.input_widget = False
                continue
            if field.type == 'many2one':
                wizard.input_widget = 'reference'
                comodel = Model.search([('model', '=', field.comodel_name)], limit=1)
                wizard.comodel_id = comodel
                wizard.value_hint = _('Pick a "%(model)s" record (%(technical)s).',
                                      model=comodel.name or field.comodel_name,
                                      technical=field.comodel_name)
            elif field.type == 'selection':
                # Values defined as a plain list are mirrored in
                # ir.model.fields.selection, so they can be picked from a
                # dropdown. Values computed by a method are not: those are
                # typed in, and validated against the live list below.
                from_db = isinstance(field.selection, (list, tuple))
                wizard.input_widget = 'selection' if from_db else 'selection_free'
                wizard.value_hint = ', '.join(
                    key for key, _label in wizard._field_selection(field)) or False
            elif field.type == 'monetary':
                wizard.input_widget = 'float'
            else:
                wizard.input_widget = field.type

    # ------------------------------------------------------------------
    # The value to write
    # ------------------------------------------------------------------
    def _write_value(self, field):
        """The value to write, validated against the target field."""
        self.ensure_one()
        if self.clear_value:
            if field.required:
                raise UserError(
                    _('"%s" is required: it cannot be emptied.', field.string))
            return False
        ftype = field.type
        if ftype == 'char':
            value = self.value_char
        elif ftype == 'text':
            value = self.value_text
        elif ftype == 'html':
            value = self.value_html
        elif ftype == 'integer':
            return self.value_integer
        elif ftype in ('float', 'monetary'):
            return self.value_float
        elif ftype == 'boolean':
            return self.value_boolean
        elif ftype == 'date':
            value = self.value_date
        elif ftype == 'datetime':
            value = self.value_datetime
        elif ftype == 'selection':
            allowed = [key for key, _label in self._field_selection(field)]
            if self.input_widget == 'selection':
                value = self.value_selection_id.value
                if value and self.value_selection_id.field_id != self.field_id:
                    raise UserError(
                        _('That value belongs to "%s", not to the field being updated.',
                          self.value_selection_id.field_id.name))
            else:
                value = (self.value_selection_free or '').strip()
            if value and value not in allowed:
                raise UserError(
                    _('"%(value)s" is not a valid value for %(field)s. Allowed: %(allowed)s',
                      value=value, field=field.string, allowed=', '.join(allowed)))
        elif ftype == 'many2one':
            record = self.value_reference
            if record:
                if record._name != field.comodel_name:
                    raise UserError(
                        _('%(field)s expects a %(expected)s record, not a %(given)s one.',
                          field=field.string, expected=field.comodel_name, given=record._name))
                # the picker filters client-side only: check the record really
                # exists and that this user may read it before linking to it
                if not record.exists():
                    raise UserError(_('The record chosen as the new value no longer exists.'))
                if not self._record_readable(record):
                    raise UserError(
                        _('You are not allowed to use that record as a value.'))
            value = record.id if record else False
        else:
            raise UserError(_('Fields of type "%s" are not supported.', ftype))
        if not value:
            raise UserError(
                _('Enter a value for "%s", or tick "Clear the value" to empty it.',
                  field.string))
        return value

    def _format_value(self, field, value):
        """A short, human-readable rendering of a stored value."""
        self.ensure_one()
        if field.type == 'many2one':
            return value.display_name if value else str(_('(empty)'))
        if value is False or value is None or value == '':
            return str(_('(empty)'))
        if field.type == 'boolean':
            return str(_('Yes')) if value else str(_('No'))
        if field.type == 'selection':
            labels = dict(self._field_selection(field))
            return '%s (%s)' % (labels.get(value, value), value)
        text = str(value)
        return text if len(text) <= 120 else text[:117] + '...'

    @api.depends('field_id', 'clear_value', 'value_char', 'value_text', 'value_html',
                 'value_integer', 'value_float', 'value_boolean', 'value_date',
                 'value_datetime', 'value_selection_id', 'value_selection_free',
                 'value_reference')
    def _compute_value_display(self):
        for wizard in self:
            field = wizard._safe_field()
            if not field:
                wizard.value_display = False
                continue
            try:
                value = wizard._write_value(field)
            except UserError:
                wizard.value_display = False
                continue
            if field.type == 'many2one':
                value = wizard.value_reference
            wizard.value_display = wizard._format_value(field, value)

    # ------------------------------------------------------------------
    # Which records are concerned
    # ------------------------------------------------------------------
    def _partition_records(self):
        """(readable records, deleted count, invisible count) of the selection.

        ``search`` applies the user's record rules, so records they may not see
        simply do not come back - they are reported, never written.
        """
        self.ensure_one()
        model = self.env[self._target_model_name()].with_context(active_test=False)
        ids = self._record_ids()
        existing = model.browse(ids).exists()
        readable = model.search([('id', 'in', existing.ids)]) if existing else model
        return readable, len(set(ids)) - len(existing), len(existing) - len(readable)

    def _change_domain(self, field, value):
        """Domain matching the records whose value differs from the new one."""
        self.ensure_one()
        return [(field.name, '!=', value)]

    @api.depends('state', 'field_id', 'res_model', 'record_ids_json', 'clear_value',
                 'value_char', 'value_text', 'value_html', 'value_integer',
                 'value_float', 'value_boolean', 'value_date', 'value_datetime',
                 'value_selection_id', 'value_selection_free', 'value_reference')
    def _compute_preview(self):
        for wizard in self:
            wizard.match_count = 0
            wizard.unchanged_count = 0
            wizard.hidden_count = 0
            wizard.missing_count = 0
            if wizard.state != 'choose' or not wizard.res_model:
                continue
            field = wizard._safe_field()
            if not field:
                continue
            try:
                value = wizard._write_value(field)
            except UserError:
                continue
            readable, missing, hidden = wizard._partition_records()
            matching = readable.search_count(
                [('id', 'in', readable.ids)] + wizard._change_domain(field, value)
            ) if readable else 0
            wizard.match_count = matching
            wizard.unchanged_count = len(readable) - matching
            wizard.hidden_count = hidden
            wizard.missing_count = missing

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------
    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context),
        }

    def action_preview(self):
        """Validate everything and move to the confirmation step."""
        self.ensure_one()
        model_name = self._target_model_name()
        field = self._target_field()
        value = self._write_value(field)
        ids = self._record_ids()
        if not ids:
            raise UserError(_('Select the records to update first.'))
        if len(ids) > MAX_RECORDS:
            raise UserError(
                _('%(selected)s records selected: this action updates at most '
                  '%(max)s records at a time. Narrow the selection, or use an '
                  'import for a bigger change.',
                  selected=len(ids), max=MAX_RECORDS))
        if not self._model_writable(self.env[model_name]):
            raise UserError(_('You are not allowed to modify %s records.',
                              self.env[model_name]._description or model_name))
        readable, missing, hidden = self._partition_records()
        matching = readable.search_count(
            [('id', 'in', readable.ids)] + self._change_domain(field, value)
        ) if readable else 0
        self.write({'state': 'confirm', 'preview_count': matching})
        return self._reopen()

    def action_back(self):
        self.ensure_one()
        self.write({'state': 'choose'})
        return self._reopen()

    def action_apply(self):
        """Write the value, one savepoint per record."""
        self.ensure_one()
        if self.state != 'confirm':
            # the confirmation step is a rule, not a screen: apply is refused
            # until the model, field, value and count have been shown.
            raise UserError(_('Review and confirm the change before applying it.'))
        model_name = self._target_model_name()
        # never trust what came back from the client: the field is validated
        # against the model and against the user's rights all over again
        field = self._target_field()
        value = self._write_value(field)
        model = self.env[model_name]
        if not self._model_writable(model):
            raise UserError(_('You are not allowed to modify %s records.',
                              model._description or model_name))
        ids = self._record_ids()
        if not ids:
            raise UserError(_('Select the records to update first.'))
        # the cap is re-checked here too, not only at preview time
        if len(ids) > MAX_RECORDS:
            raise UserError(
                _('%(selected)s records selected: this action updates at most '
                  '%(max)s records at a time.', selected=len(ids), max=MAX_RECORDS))
        readable, missing, hidden = self._partition_records()
        records = readable.search(
            [('id', 'in', readable.ids)] + self._change_domain(field, value)
        ) if readable else readable
        unchanged = len(readable) - len(records)

        new_label = self._format_value(
            field, self.value_reference if field.type == 'many2one' else value)
        updated = skipped = failed = 0
        denied, errors = [], []
        for record in records:
            # the note quotes the previous value, so build it before writing
            body = self._note_body(record, field, new_label) if self.log_note else False
            try:
                # one savepoint per record: a single failure never aborts the batch
                with self.env.cr.savepoint():
                    record.write({field.name: value})
            except AccessError:
                # the user may not write this record: report it, never sudo() it
                skipped += 1
                denied.append(self._record_label(record))
            except psycopg2.OperationalError:
                # serialization failure / deadlock: let Odoo retry the request
                raise
            except Exception as err:  # noqa: BLE001 - one bad record, not the batch
                _logger.warning('Mass update of %s(%s).%s failed: %s',
                                model_name, record.id, field.name, err)
                failed += 1
                errors.append((self._record_label(record), self._error_label(err)))
            else:
                updated += 1
                if body and hasattr(record, 'message_post'):
                    self._log_note(record, body)

        self.write({
            'state': 'done',
            'updated_count': updated,
            'skipped_count': skipped + hidden + missing,
            'failed_count': failed,
            'result_details': self._result_details(
                updated, unchanged, hidden, missing, denied, errors),
        })
        return self._reopen()

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    def _record_label(self, record):
        self.ensure_one()
        try:
            label = record.display_name or ''
        except AccessError:
            label = ''
        label = label or '%s(%s)' % (record._name, record.id)
        return label if len(label) <= 60 else label[:57] + '...'

    @api.model
    def _error_label(self, err):
        text = str(err).strip()
        text = text.splitlines()[0] if text else type(err).__name__
        return text if len(text) <= 120 else text[:117] + '...'

    def _note_body(self, record, field, new_label):
        self.ensure_one()
        # str(): the body is stored as it is, never a translation proxy
        return str(_('Mass update: %(field)s changed from %(old)s to %(new)s.',
                     field=field.string,
                     old=self._format_value(field, record[field.name]),
                     new=new_label))

    def _log_note(self, record, body):
        """Log the note; a chatter problem must never lose the write."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                record.message_post(body=body, subtype_xmlid='mail.mt_note')
        except Exception as err:  # noqa: BLE001 - e.g. an author without an email
            _logger.warning('Could not log the mass-update note on %s(%s): %s',
                            record._name, record.id, err)

    def _result_details(self, updated, unchanged, hidden, missing, denied, errors):
        self.ensure_one()
        lines = [str(_('%s record(s) updated.', updated))]
        if unchanged:
            lines.append(str(_('%s record(s) already had this value.', unchanged)))
        if denied:
            lines.append(str(_('%(count)s record(s) skipped - you may not edit them: %(names)s',
                               count=len(denied), names=self._quote(denied))))
        if hidden:
            lines.append(str(_('%s record(s) skipped - not visible to you.', hidden)))
        if missing:
            lines.append(str(_('%s record(s) skipped - deleted in the meantime.', missing)))
        if errors:
            lines.append(str(_('%s record(s) failed:', len(errors))))
            for label, message in errors[:MAX_REPORTED]:
                lines.append('  - %s: %s' % (label, message))
            if len(errors) > MAX_REPORTED:
                lines.append(str(_('  - ... and %s more.', len(errors) - MAX_REPORTED)))
        return '\n'.join(lines)

    @api.model
    def _quote(self, labels):
        # quoted: record names often contain a comma themselves
        shown = ', '.join('"%s"' % label for label in labels[:MAX_REPORTED])
        if len(labels) > MAX_REPORTED:
            shown = '%s %s' % (shown, str(_('... and %s more', len(labels) - MAX_REPORTED)))
        return shown
