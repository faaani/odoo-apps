# -*- coding: utf-8 -*-
# Part of bulk_tag_manager. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

import psycopg2

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

MODULE = 'bulk_tag_manager'

# Many2many fields pointing at these models are plumbing, not tags.
TECHNICAL_PREFIXES = (
    'ir.', 'bus.', 'mail.', 'base_import.', 'report.', 'web_editor.',
    'web_tour.', 'iap.',
)
EXCLUDED_COMODELS = frozenset({
    'res.users', 'res.groups', 'res.company', 'res.partner', 'res.currency',
    'res.country', 'res.country.group', 'res.country.state', 'res.lang',
    'res.partner.bank',
})
# Models whose *records* never make sense as a bulk-tagging target.
TECHNICAL_MODEL_PREFIXES = TECHNICAL_PREFIXES + ('res.config', 'res.groups')
# A many2many counts as a tag field when it is *named* like one, or when it
# points at a model named like a tag model. Everything else - taxes, routes,
# any other many2many that happens to be writable - is deliberately left out:
# this module promises tags, and must not become a blind mass-editor.
TAG_FIELD_NAMES = frozenset({'tag_ids', 'tags', 'category_id', 'category_ids',
                             'categ_ids', 'label_ids', 'labels'})
TAG_FIELD_SUFFIXES = ('_tag_ids', '_tags', '_category_ids', '_categ_ids',
                      '_categories', '_label_ids')
TAG_COMODEL_SUFFIXES = ('.tag', '.tags', '.category', '.categories', '.categ',
                        '.label', '.labels')
# Safety rail for the Action-menu scan: an Odoo database with every app
# installed still stays well under this.
MAX_BOUND_MODELS = 120


class BulkTagField(models.TransientModel):
    """One line of the "Tag Field" dropdown of the wizard.

    The tag field has to be picked at runtime, from the model the user is
    standing on. The web client does not forward ``active_model`` when it loads
    the fields of a view, so a dynamic ``Selection`` cannot be built, and
    ``ir.model.fields`` is readable by administrators only - so the choices are
    materialised as transient records of this model instead. They are proposals
    only: what the user picks is re-validated against the real field of the real
    model before anything is written.
    """
    _name = 'bulk.tag.field'
    _description = 'Bulk Tag Manager: Tag Field Choice'
    _order = 'sequence, name'

    name = fields.Char(string='Field', required=True)
    sequence = fields.Integer(default=10)
    res_model = fields.Char(string='Model', required=True)
    field_name = fields.Char(string='Technical Name', required=True)
    comodel = fields.Char(string='Tag Model')


class BulkTagWizard(models.TransientModel):
    _name = 'bulk.tag.wizard'
    _description = 'Add and Remove Tags in Bulk'

    res_model = fields.Char(string='Model', readonly=True)
    record_count = fields.Integer(string='Selected Records', readonly=True)
    option_ids = fields.Many2many(
        'bulk.tag.field', string='Available Tag Fields', readonly=True)
    tag_option_id = fields.Many2one(
        'bulk.tag.field', string='Tag Field', required=True, ondelete='cascade',
        domain="[('id', 'in', option_ids)]",
        help='The field of the selected model that holds the tags. Only tag '
             'fields are listed: a many2many named like a tag field, or one '
             'pointing at a tag or category model.')
    tag_model_label = fields.Char(
        string='Tags Taken From', compute='_compute_tag_info')
    existing_tag_hint = fields.Char(
        string='Existing Tags', compute='_compute_tag_info')
    add_tag_names = fields.Char(
        string='Tags to Add',
        help='Comma-separated tag names. Matching is case-insensitive.')
    remove_tag_names = fields.Char(
        string='Tags to Remove',
        help='Comma-separated tag names. Only these tags are removed; every '
             'other tag on the record is left alone.')
    create_missing = fields.Boolean(
        string='Create Missing Tags', default=False,
        help='Create the tags to add that do not exist yet. Off by default: '
             'without it, an unknown tag name stops the run instead of '
             'silently creating a typo.')

    # ------------------------------------------------------------------
    # selection / detection
    # ------------------------------------------------------------------
    @api.model
    def _is_tag_field(self, field_name, comodel_name):
        """True for a many2many that really is a tag field.

        Either the field is named like one (``tag_ids``, ``category_id``,
        ``product_tag_ids``, ...) or it points at a model named like a tag
        model (``crm.tag``, ``res.partner.category``, ...). A plain writable
        many2many such as ``product.template.taxes_id`` is not a tag field and
        is never offered - removing a tax from five hundred products is not
        what "Add / Remove Tags" is allowed to mean.
        """
        return (field_name in TAG_FIELD_NAMES
                or field_name.endswith(TAG_FIELD_SUFFIXES)
                or comodel_name.endswith(TAG_COMODEL_SUFFIXES))

    @api.model
    def _can_read_model(self, model):
        """True when the current user may read ``model`` (never sudo)."""
        try:
            if hasattr(model, 'check_access'):
                model.check_access('read')          # 18.0+
            else:
                model.check_access_rights('read')   # 14.0 - 17.0
        except AccessError:
            return False
        return True

    @api.model
    def _tag_field_candidates(self, model_name):
        """The writable tag many2many fields of ``model_name``.

        Detection happens at runtime on ``_fields`` so the wizard works on any
        model, and ``fields_get()`` is used as the gate so fields restricted to
        groups the user does not have are never offered.
        Returns a list of ``(field_name, label, comodel_name)``.
        """
        if not model_name or model_name not in self.env:
            return []
        model = self.env[model_name]
        if model._abstract or model._transient:
            return []
        # cheap registry test first: most models have no many2many at all, and
        # the binding scan asks this question about every model of the database
        if not any(field.type == 'many2many' for field in model._fields.values()):
            return []
        try:
            descriptions = model.fields_get(attributes=['string', 'type'])
        except AccessError:
            return []
        candidates = []
        for field_name, description in descriptions.items():
            if description.get('type') != 'many2many':
                continue
            field = model._fields.get(field_name)
            if field is None or not field.store or field.readonly:
                continue
            if field.compute or field.related or field.inherited:
                continue
            comodel_name = field.comodel_name
            if not comodel_name or comodel_name not in self.env:
                continue
            if comodel_name.startswith(TECHNICAL_PREFIXES) or comodel_name in EXCLUDED_COMODELS:
                continue
            # a tag field, not just any many2many the user happens to be
            # allowed to write
            if not self._is_tag_field(field_name, comodel_name):
                continue
            comodel = self.env[comodel_name]
            if comodel._abstract or comodel._transient:
                continue
            # tags are resolved by name, so the target model needs one
            if 'name' not in comodel._fields:
                continue
            if not self._can_read_model(comodel):
                continue
            candidates.append((field_name, description.get('string') or field_name, comodel_name))
        candidates.sort(key=lambda candidate: (candidate[1], candidate[0]))
        return candidates

    @api.model
    def _build_options(self, model_name):
        """Materialise the tag fields of ``model_name`` as dropdown choices."""
        candidates = self._tag_field_candidates(model_name)
        return self.env['bulk.tag.field'].create([{
            'name': label,
            'sequence': index,
            'res_model': model_name,
            'field_name': field_name,
            'comodel': comodel_name,
        } for index, (field_name, label, comodel_name) in enumerate(candidates)])

    def _target_model(self):
        """The model the wizard acts on: the Action-menu selection."""
        model_name = self.env.context.get('active_model')
        if not model_name and len(self) == 1:
            model_name = self.res_model
        return model_name

    @api.model
    def _context_record_ids(self):
        """Selected ids, tolerating the single-record (active_id) binding."""
        ids = self.env.context.get('active_ids') or []
        if not ids and self.env.context.get('active_id'):
            ids = [self.env.context['active_id']]
        return list(ids)

    # ------------------------------------------------------------------
    # defaults / computes
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        result = super(BulkTagWizard, self).default_get(fields_list)
        model_name = self.env.context.get('active_model')
        candidates = self._tag_field_candidates(model_name)
        if model_name and not candidates:
            raise UserError(_(
                'No tag field was found on "%s".\n\nThis wizard needs a '
                'many2many field you are allowed to write, pointing at a model '
                'that has a name (a tag or category model).', model_name))
        result.update(res_model=model_name, record_count=len(self._context_record_ids()))
        if candidates and not result.get('tag_option_id'):
            options = self._build_options(model_name)
            result['option_ids'] = [(6, 0, options.ids)]
            # preselect the most tag-like field, so one-tag-field models
            # (the usual case) need no choice at all
            result['tag_option_id'] = options[:1].id
        return result

    @api.depends('tag_option_id', 'tag_option_id.field_name',
                 'tag_option_id.res_model', 'res_model')
    def _compute_tag_info(self):
        for wizard in self:
            wizard.tag_model_label = False
            wizard.existing_tag_hint = False
            comodel_name = wizard._comodel_of(wizard.tag_option_id)
            if not comodel_name:
                continue
            comodel = self.env[comodel_name]
            wizard.tag_model_label = '%s (%s)' % (comodel._description or comodel_name,
                                                  comodel_name)
            if not self._can_read_model(comodel):
                continue
            existing = comodel.search([], limit=21)
            names = [tag.name for tag in existing[:20] if tag.name]
            if not names:
                wizard.existing_tag_hint = _('No tag exists yet on this model.')
            elif len(existing) > 20:
                wizard.existing_tag_hint = '%s, ...' % ', '.join(names)
            else:
                wizard.existing_tag_hint = ', '.join(names)

    def _comodel_of(self, option):
        """Comodel of ``option``, but only if it is a real candidate.

        This is the server-side re-validation, and the reason the dropdown
        choices can be plain user-writable records: the field name that comes
        back from the client is looked up again in ``_fields`` of the model the
        user is really standing on. A forged name - a field that is not a
        writable many2many, or one belonging to another model - resolves to
        nothing here and the run is refused.
        """
        model_name = self._target_model()
        if not option or not model_name or option.res_model != model_name:
            return False
        for name, _label, comodel_name in self._tag_field_candidates(model_name):
            if name == option.field_name:
                return comodel_name
        return False

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @api.model
    def _split_names(self, raw):
        """Comma-separated input -> list of names, de-duplicated (no case)."""
        names, seen = [], set()
        for chunk in (raw or '').split(','):
            name = chunk.strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            names.append(name)
        return names

    @api.model
    def _name_matches(self, comodel, name):
        """Tags of ``comodel`` whose name equals ``name``, ignoring case.

        ``=ilike`` is a SQL ILIKE, not an equality: an unescaped ``%`` or ``_``
        typed by the user would match other tags ("100%" would silently resolve
        to "100% Complete"). The pattern is escaped, and the result is then
        compared in Python so the match is a real case-insensitive equality on
        every series, whatever the database does with accents.
        """
        pattern = name.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        matches = comodel.search([('name', '=ilike', pattern)], limit=20)
        return matches.filtered(lambda tag: (tag.name or '').strip().lower() == name.lower())

    def _resolve_tags(self, comodel_name, raw, create_missing):
        """Resolve tag names to records of ``comodel_name``.

        Everything is resolved *before* any record is written, so a typo can
        never leave half of the selection updated.
        """
        comodel = self.env[comodel_name]
        tags = comodel.browse()
        unknown, ambiguous = [], []
        for name in self._split_names(raw):
            matches = self._name_matches(comodel, name)
            if len(matches) > 1:
                ambiguous.append(name)
            elif matches:
                tags |= matches
            elif create_missing:
                try:
                    tags |= comodel.create({'name': name})
                except AccessError:
                    raise UserError(_(
                        'You are not allowed to create tags on %(model)s, so '
                        '"%(tag)s" cannot be created.',
                        model=comodel._description or comodel_name, tag=name))
            else:
                unknown.append(name)
        if ambiguous:
            raise UserError(_(
                'Several tags are named %s. Tags are matched by name, so please '
                'make the name unique first.',
                ', '.join('"%s"' % name for name in ambiguous)))
        if unknown:
            raise UserError(_(
                'No tag named %(names)s exists on %(model)s.\n\nCheck the '
                'spelling, or tick "Create Missing Tags" to create the tags you '
                'want to add.',
                names=', '.join('"%s"' % name for name in unknown),
                model=comodel._description or comodel_name))
        return tags

    @api.model
    def _check_write_access(self, record):
        """Raise AccessError when the user may not write ``record``."""
        if hasattr(record, 'check_access'):
            record.check_access('write')        # 18.0+
        else:
            record.check_access_rights('write')  # 14.0 - 17.0
            record.check_access_rule('write')

    @api.model
    def _invalidate(self):
        """Drop cached values after a failed record.

        ``cr.savepoint()`` already clears the cache when it rolls back, on
        every supported series; this is the belt to that pair of braces, and it
        also covers the failures raised before the savepoint is even entered.
        """
        if hasattr(self.env, 'invalidate_all'):
            self.env.invalidate_all()   # 16.0+
        else:
            self.invalidate_cache()     # 14.0 / 15.0

    # ------------------------------------------------------------------
    # action
    # ------------------------------------------------------------------
    def action_apply(self):
        """Apply the tag changes and report what really happened."""
        return self._notify(**self._apply_tags())

    def _apply_tags(self):
        """Do the work, return the counters. Split out so it stays testable."""
        self.ensure_one()
        model_name = self._target_model()
        record_ids = self._context_record_ids()
        if not model_name or not record_ids:
            raise UserError(_('Select the records you want to tag first.'))

        # Re-validate the field server-side: never trust the value that came
        # back from the client.
        field_name = self.tag_option_id.field_name
        comodel_name = self._comodel_of(self.tag_option_id)
        if not comodel_name:
            raise UserError(_(
                '"%(field)s" is not a tag field of %(model)s, or you are not '
                'allowed to use it.', field=field_name or '', model=model_name))

        tags_to_add = self._resolve_tags(comodel_name, self.add_tag_names, self.create_missing)
        tags_to_remove = self._resolve_tags(comodel_name, self.remove_tag_names, False)
        if not tags_to_add and not tags_to_remove:
            raise UserError(_('Enter at least one tag to add or one tag to remove.'))
        both = tags_to_add & tags_to_remove
        if both:
            raise UserError(_(
                'The same tag cannot be added and removed in one run: %s.',
                ', '.join(both.mapped('name'))))

        records = self.env[model_name].browse(record_ids).exists()
        if not records:
            raise UserError(_('The selected records no longer exist.'))

        add_ids = tags_to_add.ids
        remove_ids = tags_to_remove.ids
        changed = unchanged = skipped = failed = 0
        for record in records:
            try:
                self._check_write_access(record)
                before = set(record[field_name].ids)
                # (4, id) / (3, id) only - NEVER (6, 0, ids), which would
                # replace the whole tag set and wipe tags this run never
                # mentioned.
                commands = [(4, tag_id) for tag_id in add_ids if tag_id not in before]
                commands += [(3, tag_id) for tag_id in remove_ids if tag_id in before]
                if not commands:
                    # already in the wanted state: a clean no-op, and no write
                    # at all - so no savepoint and no flush either
                    unchanged += 1
                    continue
                # one savepoint per written record: a record that refuses the
                # write must not roll back the ones already done
                with self.env.cr.savepoint():
                    record.write({field_name: commands})
                    after = set(record[field_name].ids)
                if after != before:
                    changed += 1
                else:
                    unchanged += 1
            except AccessError:
                self._invalidate()
                skipped += 1
            except (UserError, ValidationError, psycopg2.Error) as error:
                self._invalidate()
                failed += 1
                _logger.info('bulk_tag_manager: %s(%s) refused the tag update: %s',
                             model_name, record.id, error)
        return {'changed': changed, 'unchanged': unchanged,
                'skipped': skipped, 'failed': failed}

    @api.model
    def _notify(self, changed, unchanged, skipped, failed):
        parts = [_('%s record(s) updated.', changed)]
        if unchanged:
            parts.append(_('%s already had the right tags.', unchanged))
        if skipped:
            parts.append(_('%s skipped (access denied).', skipped))
        if failed:
            parts.append(_('%s refused the change.', failed))
        problem = bool(skipped or failed)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning' if problem else 'success',
                'sticky': problem,
                'title': _('Tags updated'),
                'message': ' '.join(parts),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    # ------------------------------------------------------------------
    # Action-menu bindings
    # ------------------------------------------------------------------
    @api.model
    def _is_bindable_model(self, model_name):
        """Only models that really carry tags get the Action-menu entry."""
        if model_name.startswith(TECHNICAL_MODEL_PREFIXES) or model_name == self._name:
            return False
        return bool(self._tag_field_candidates(model_name))

    @api.model
    def _sync_action_bindings(self):
        """Put "Add / Remove Tags" on every installed model that has tags.

        Called from the module's data file, so it runs on install *and* on
        every upgrade: installing CRM afterwards only needs an upgrade of this
        module for leads to get the entry too. Each action is registered under
        this module's external ids, so uninstalling removes them all.
        """
        if not (self.env.su or self.env.user.has_group('base.group_system')):
            raise AccessError(_('Only administrators can rebuild the Tags action menu.'))
        data = self.env['ir.model.data']
        existing = set(data.search([('module', '=', MODULE),
                                    ('model', '=', 'ir.actions.act_window')]).mapped('name'))
        created = 0
        for model in self.env['ir.model'].search([('transient', '=', False)], order='model'):
            if len(existing) + created >= MAX_BOUND_MODELS:
                _logger.info('bulk_tag_manager: binding limit of %s models reached',
                             MAX_BOUND_MODELS)
                break
            xml_id = 'action_bulk_tag_%s' % model.model.replace('.', '_')
            if xml_id in existing:
                continue
            if not self._is_bindable_model(model.model):
                continue
            action = self.env['ir.actions.act_window'].create({
                'name': _('Add / Remove Tags'),
                'res_model': self._name,
                'view_mode': 'form',
                'target': 'new',
                'binding_model_id': model.id,
                'binding_view_types': 'list',
            })
            data.create({
                'module': MODULE,
                'name': xml_id,
                'model': 'ir.actions.act_window',
                'res_id': action.id,
                'noupdate': True,
            })
            created += 1
        _logger.info('bulk_tag_manager: %s model(s) gained the Tags action menu', created)
        return created
