# -*- coding: utf-8 -*-
# Part of default_value_manager. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import json
import logging
from collections import defaultdict

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# A rendered value never fills the whole list cell: long text and JSON blobs are
# cut here and the cut is made visible with an ellipsis. Stated in the field help.
MAX_VALUE_CHARS = 200
# Number of target names rendered for a x2many default before "and N more".
X2MANY_NAME_LIMIT = 10

# One row per ir.default row, SAME id, so an entry maps 1:1 onto the ir.default
# record it describes. That is what makes deleting an entry a plain ORM unlink
# on ir.default, with its access rights, its record rules and its cache
# invalidation applied by core.
ENTRY_VIEW_SQL = """
    SELECT d.id                                     AS id,
           d.field_id                               AS field_id,
           f.model                                  AS model_name,
           f.name                                   AS field_name,
           f.ttype                                  AS field_type,
           f.relation                               AS field_relation,
           f.model || '.' || f.name                 AS complete_name,
           m.id                                     AS model_id,
           d.user_id                                AS user_id,
           d.company_id                             AS company_id,
           CASE WHEN d.user_id IS NULL
                THEN 'all' ELSE 'user' END          AS user_scope,
           CASE WHEN d.company_id IS NULL
                THEN 'all' ELSE 'company' END       AS company_scope,
           d.condition                              AS condition,
           d.json_value                             AS json_value,
           d.create_uid                             AS create_uid,
           d.create_date                            AS create_date,
           d.write_date                             AS write_date
      FROM ir_default d
      JOIN ir_model_fields f ON f.id = d.field_id
      LEFT JOIN ir_model m ON m.model = f.model
"""


class DefaultValueEntry(models.Model):
    _name = 'default.value.entry'
    _description = 'Default Value'
    _auto = False
    _rec_name = 'complete_name'
    _order = 'model_name, field_name, id'

    model_name = fields.Char(
        string='Model', readonly=True,
        help='Technical name of the model the default applies to.',
    )
    model_id = fields.Many2one(
        'ir.model', string='Model Description', readonly=True,
        help='The model as registered in the database. Empty when the model is '
             'no longer installed.',
    )
    field_id = fields.Many2one(
        'ir.model.fields', string='Field Definition', readonly=True,
        help='The field definition the default is attached to. It still exists '
             'even for an orphaned entry, which is exactly why the entry survives.',
    )
    field_name = fields.Char(
        string='Field', readonly=True,
        help='Technical name of the field that gets pre-filled.',
    )
    # read through the relation, never from the view: on 16.0+ the column is a
    # translated jsonb one and only the ORM knows which language to serve
    field_label = fields.Char(
        related='field_id.field_description', string='Field Description', readonly=True,
        help='Label of the field the default pre-fills.',
    )
    field_type = fields.Char(
        string='Field Type', readonly=True,
        help='Type of the field, as recorded for it in the database.',
    )
    field_relation = fields.Char(
        string='Target Model', readonly=True,
        help='For a relational field, the model of the record(s) the default points to.',
    )
    complete_name = fields.Char(
        string='Default On', readonly=True,
        help='The "model.field" the default applies to.',
    )
    user_id = fields.Many2one(
        'res.users', string='User', readonly=True,
        help='The only user this default applies to. Empty means it applies to '
             'every user.',
    )
    company_id = fields.Many2one(
        'res.company', string='Company', readonly=True,
        help='The only company this default applies to. Empty means it applies '
             'to every company.',
    )
    user_scope = fields.Selection(
        [('all', 'All users'), ('user', 'One user')],
        string='User Scope', readonly=True,
    )
    company_scope = fields.Selection(
        [('all', 'All companies'), ('company', 'One company')],
        string='Company Scope', readonly=True,
    )
    condition = fields.Char(
        string='Condition', readonly=True,
        help='Optional condition the default is restricted to, in the form '
             '"other_field=value". Empty for an unconditional default.',
    )
    json_value = fields.Char(
        string='Stored Value (JSON)', readonly=True,
        help='The raw value exactly as ir.default stores it, in JSON.',
    )
    create_uid = fields.Many2one('res.users', string='Set By', readonly=True)
    create_date = fields.Datetime(string='Set On', readonly=True)
    write_date = fields.Datetime(string='Last Updated', readonly=True)

    value_display = fields.Char(
        string='Value', compute='_compute_value_info', search='_search_value_display',
        help='The stored value in readable form: the name of the target record '
             'for a many2one, Yes/No for a boolean, the label of a selection. '
             'Values longer than %s characters are shortened.' % MAX_VALUE_CHARS,
    )
    entry_status = fields.Selection(
        [
            ('ok', 'Applies'),
            ('orphan_model', 'Orphaned - model gone'),
            ('orphan_field', 'Orphaned - field gone'),
            ('missing_target', 'Target record deleted'),
            ('invalid_value', 'Unreadable value'),
        ],
        string='Status', compute='_compute_value_info', search='_search_entry_status',
        help='"Orphaned" entries survive in the database while the model or the '
             'field they were set on no longer exists, so they can never apply '
             'again. "Target record deleted" is a default pointing at a record '
             'that has been removed. "Unreadable value" is a stored value that '
             'is not valid JSON.',
    )
    is_orphaned = fields.Boolean(
        string='Orphaned', compute='_compute_value_info', search='_search_is_orphaned',
        help='Ticked when the model or the field this default was set on no '
             'longer exists in this database.',
    )

    @api.model
    def _entry_view_sql(self):
        """The SELECT behind this read-only view: a module constant."""
        return ENTRY_VIEW_SQL

    def init(self):
        # Read-only database view over ir_default. The two interpolated values
        # are self._table, derived from _name, and a module constant - no user
        # input reaches this statement.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            'CREATE VIEW %s AS (%s)' % (self._table, self._entry_view_sql()))

    # ------------------------------------------------------------------
    # Value resolution - batched per target model, never one query per row
    # ------------------------------------------------------------------
    @api.model
    def _shorten(self, text):
        text = '' if text is None else str(text)
        if len(text) > MAX_VALUE_CHARS:
            return text[:MAX_VALUE_CHARS] + '...'
        return text

    @api.model
    def _value_ids(self, value):
        """Record ids referenced by a stored default value.

        Handles a plain id, a list of ids, and the x2many command lists the web
        client writes, e.g. ``[[6, 0, [1, 2]]]``.
        """
        if isinstance(value, bool) or value is None:
            return []
        if isinstance(value, int):
            return [value]
        ids = []
        if isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, bool):
                    continue
                if isinstance(item, int):
                    ids.append(item)
                elif isinstance(item, (list, tuple)) and len(item) == 3 and item[0] in (4, 6):
                    if item[0] == 4 and isinstance(item[1], int):
                        ids.append(item[1])
                    elif item[0] == 6 and isinstance(item[2], (list, tuple)):
                        ids.extend(i for i in item[2] if isinstance(i, int))
        return ids

    @api.model
    def _target_info(self, comodel, ids):
        """``(existing ids, {id: display name})`` for one target model.

        ``existing`` is ``None`` when nothing can be checked, i.e. the model is
        not installed any more. Names are read as the current user, so record
        rules apply; a model the user may not read yields no name instead of
        breaking the whole list.
        """
        if not comodel or comodel not in self.env or not ids:
            return None, {}
        model = self.env[comodel]
        if model._abstract or model._transient:
            return None, {}
        sorted_ids = sorted(ids)
        try:
            with self.env.cr.savepoint():
                # exists() is a plain SELECT id: it tells deleted apart from
                # unreadable, which an ORM read could not.
                existing = set(model.browse(sorted_ids).exists().ids)
        except Exception:  # pylint: disable=broad-except
            _logger.debug('default_value_manager: cannot check %s ids', comodel, exc_info=True)
            return None, {}
        names = {}
        try:
            with self.env.cr.savepoint():
                for record in model.with_context(
                        active_test=False, prefetch_fields=False).browse(sorted(existing)):
                    names[record.id] = record.display_name
        except Exception:  # pylint: disable=broad-except
            # access error, or a display name that breaks on half-deleted data:
            # neither must kill the list
            _logger.debug('default_value_manager: cannot read %s names', comodel, exc_info=True)
            names = {}
        return existing, names

    @api.model
    def _selection_labels(self, model_name, field_name):
        """``{key: label}`` of a selection field, or ``{}`` when unavailable."""
        if model_name not in self.env:
            return {}
        field = self.env[model_name]._fields.get(field_name)
        if field is None or field.type != 'selection':
            return {}
        try:
            return dict(field._description_selection(self.env))
        except Exception:  # pylint: disable=broad-except
            _logger.debug('default_value_manager: cannot read selection of %s.%s',
                          model_name, field_name, exc_info=True)
            return {}

    def _resolve(self):
        """``{entry id: (status, readable value)}`` for the entries in ``self``.

        Target records are looked up once per target model, whatever the number
        of entries pointing at it.
        """
        rows = {}
        wanted = defaultdict(set)
        for entry in self:
            model_name = entry.model_name
            field_name = entry.field_name
            field = None
            status = 'ok'
            if not model_name or model_name not in self.env:
                status = 'orphan_model'
            else:
                field = self.env[model_name]._fields.get(field_name)
                if field is None:
                    status = 'orphan_field'
            try:
                value = json.loads(entry.json_value) if entry.json_value else None
            except (TypeError, ValueError):
                # a value written outside ir.default's own JSON constraint
                rows[entry.id] = ('invalid_value', None, None, None)
                continue
            ftype = field.type if field is not None else (entry.field_type or '')
            comodel = None
            if ftype in ('many2one', 'many2many', 'one2many'):
                comodel = field.comodel_name if field is not None else entry.field_relation
            rows[entry.id] = (status, ftype, comodel, value)
            if comodel:
                ids = self._value_ids(value)
                if ids:
                    wanted[comodel].update(ids)

        targets = {comodel: self._target_info(comodel, ids) for comodel, ids in wanted.items()}

        result = {}
        for entry in self:
            status, ftype, comodel, value = rows[entry.id]
            if status == 'invalid_value':
                result[entry.id] = ('invalid_value', self._shorten(entry.json_value))
                continue
            display, missing = self._render(entry, ftype, comodel, value, targets)
            if missing and status == 'ok':
                status = 'missing_target'
            result[entry.id] = (status, display)
        return result

    def _render(self, entry, ftype, comodel, value, targets):
        """``(readable value, target missing)`` for one entry."""
        if ftype == 'boolean':
            return (_('Yes') if value else _('No')), False
        if value is None or value is False or value == '':
            return _('No value'), False
        if ftype in ('many2one', 'many2many', 'one2many') and comodel:
            existing, names = targets.get(comodel, (None, {}))
            ids = self._value_ids(value)
            if not ids:
                return self._shorten(json.dumps(value)), False
            missing = existing is not None and any(i not in existing for i in ids)
            labels = []
            for target_id in ids[:X2MANY_NAME_LIMIT]:
                if existing is not None and target_id not in existing:
                    labels.append(_('deleted record #%s', target_id))
                elif names.get(target_id):
                    labels.append(names[target_id])
                elif existing is None:
                    labels.append(_('%(model)s #%(id)s (model not installed)',
                                    model=comodel, id=target_id))
                else:
                    labels.append(_('#%s (no access to the name)', target_id))
            if len(ids) > X2MANY_NAME_LIMIT:
                labels.append(_('and %s more', len(ids) - X2MANY_NAME_LIMIT))
            return self._shorten(', '.join(labels)), missing
        if ftype == 'selection':
            labels = self._selection_labels(entry.model_name, entry.field_name)
            # a legacy row may hold anything at all, including a value that is
            # not even hashable: looking it up must not raise
            label = labels.get(value) if isinstance(value, (str, int, float)) else None
            if label:
                return self._shorten('%s (%s)' % (label, value)), False
            return self._shorten(value), False
        if ftype == 'binary':
            return _('(binary data)'), False
        if isinstance(value, (dict, list, tuple)):
            return self._shorten(json.dumps(value, ensure_ascii=False)), False
        return self._shorten(value), False

    @api.depends('json_value', 'model_name', 'field_name', 'field_type', 'field_relation')
    def _compute_value_info(self):
        resolved = self._resolve()
        for entry in self:
            status, display = resolved.get(entry.id, ('invalid_value', False))
            entry.entry_status = status
            entry.value_display = display
            entry.is_orphaned = status in ('orphan_model', 'orphan_field')

    # ------------------------------------------------------------------
    # Search methods for the computed columns
    # ------------------------------------------------------------------
    def _all_resolved(self):
        """``{id: (status, value)}`` for every entry the user may read.

        ir.default holds a handful of rows in any real database (one per
        default someone set), so resolving them all is one read plus one lookup
        per distinct target model.
        """
        return self.with_context(active_test=False).search([])._resolve()

    @api.model
    def _search_values(self, value):
        """The right-hand side of a domain leaf as a set of plain values.

        19.0's domain optimiser rewrites ``=``/``!=`` into ``in``/``not in``
        and hands over an OrderedSet; earlier series pass a bare value or a
        list. All three end up here as a set.
        """
        if isinstance(value, (str, bytes)) or not hasattr(value, '__iter__'):
            return {value}
        return set(value)

    def _search_entry_status(self, operator, value):
        if operator not in ('=', '!=', 'in', 'not in'):
            raise UserError(_('"Status" can only be searched with =, !=, in or not in.'))
        values = self._search_values(value)
        known = {'ok', 'orphan_model', 'orphan_field', 'missing_target', 'invalid_value'}
        unknown = values - known
        if unknown:
            raise UserError(_('Unknown default value status: %s',
                              ', '.join(sorted(map(str, unknown)))))
        matched = [entry_id for entry_id, (status, _display) in self._all_resolved().items()
                   if status in values]
        positive = operator in ('=', 'in')
        return [('id', 'in' if positive else 'not in', sorted(matched))]

    def _search_is_orphaned(self, operator, value):
        if operator not in ('=', '!=', 'in', 'not in'):
            raise UserError(_('"Orphaned" can only be searched with = or !=.'))
        orphan_ids = [entry_id for entry_id, (status, _display) in self._all_resolved().items()
                      if status in ('orphan_model', 'orphan_field')]
        truthy = any(bool(item) for item in self._search_values(value))
        wanted = truthy if operator in ('=', 'in') else not truthy
        return [('id', 'in' if wanted else 'not in', sorted(orphan_ids))]

    def _search_value_display(self, operator, value):
        positive_op = {
            '=': '=', 'in': '=', 'like': 'like', 'ilike': 'ilike',
            '!=': '=', 'not in': '=', 'not like': 'like', 'not ilike': 'ilike',
        }.get(operator)
        values = self._search_values(value)
        if not positive_op or not all(isinstance(item, str) for item in values):
            raise UserError(_(
                'The readable value can only be searched with a text operator '
                '(=, !=, like, ilike).'))
        needles = values if positive_op == '=' else {item.lower() for item in values}
        matched = []
        for entry_id, (_status, display) in self._all_resolved().items():
            display = display or ''
            if positive_op == '=':
                hit = display in needles
            else:
                hit = any(needle in display.lower() for needle in needles)
            if hit:
                matched.append(entry_id)
        positive = operator in ('=', 'in', 'like', 'ilike')
        return [('id', 'in' if positive else 'not in', sorted(matched))]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_delete_defaults(self):
        """Delete the ir.default rows behind the selected entries.

        Only the default values themselves are removed: no record, no field and
        no configuration is touched. The affected fields simply stop
        pre-filling.
        """
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only Settings administrators may delete default values.'))
        entries = self.exists()
        if not entries:
            raise UserError(_('Select at least one default value to delete.'))
        # Reading the entries enforces this model's access rights AND its record
        # rules, so an administrator restricted to some companies can never
        # delete a default the list does not show them - ir.default itself
        # carries no company rule.
        entries.read(['complete_name'])
        # unlink on ir.default is access-checked as the current user, and core
        # clears the default-value cache from there.
        self.env['ir.default'].browse(entries.ids).exists().unlink()
        return {'type': 'ir.actions.act_window_close'}
