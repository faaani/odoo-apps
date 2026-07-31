# -*- coding: utf-8 -*-
# Part of field_help_editor. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import threading
from contextlib import contextmanager

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

# Core's translation helpers write the value back through the public write() to
# fire override hooks. That nested write is not a user change: suspend the
# bookkeeping for its duration. A thread-local is used on purpose - a context
# key would be settable by any RPC caller, which could silently disable the
# recording of a real customization.
_reentrancy = threading.local()


@contextmanager
def _suspend_bookkeeping():
    previous = getattr(_reentrancy, 'active', False)
    _reentrancy.active = True
    try:
        yield
    finally:
        _reentrancy.active = previous

# Columns every model carries for bookkeeping: never interesting to relabel,
# hidden from the editor unless the administrator asks for them.
# ('__last_update' only exists up to 16.0; harmless to keep listed afterwards.)
BOOKKEEPING_FIELDS = (
    'id',
    'create_uid',
    'create_date',
    'write_uid',
    'write_date',
    'display_name',
    '__last_update',
)
# The two translatable columns this module lets an administrator change.
LABEL_KEYS = ('field_description', 'help')

TRUE_DOMAIN = [(1, '=', 1)]
FALSE_DOMAIN = [(0, '=', 1)]


def _wanted_values(operator, value):
    """Return the set of boolean values matched by ``operator``/``value``.

    Search methods are called with ``=``/``!=`` on older versions and may be
    called with ``in``/``not in`` on newer ones.
    """
    if operator in ('=', '!='):
        wanted = {bool(value)}
        if operator == '!=':
            wanted = {True, False} - wanted
    elif operator in ('in', 'not in'):
        values = value if isinstance(value, (list, tuple, set)) else [value]
        wanted = {bool(item) for item in values}
        if operator == 'not in':
            wanted = {True, False} - wanted
    else:
        raise NotImplementedError("Unsupported search operator %r" % (operator,))
    return wanted


def _bool_domain(wanted, true_domain, false_domain):
    if wanted == {True, False}:
        return TRUE_DOMAIN
    if not wanted:
        return FALSE_DOMAIN
    return true_domain if True in wanted else false_domain


class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    fhe_customization_ids = fields.One2many(
        'field.help.customization', 'field_id', string='Label Customizations')
    fhe_customized = fields.Boolean(
        string='Customized', compute='_compute_fhe_customized',
        search='_search_fhe_customized',
        help="The label or the tooltip of this field was changed from this "
             "database, in at least one language.")
    fhe_is_technical = fields.Boolean(
        string='Bookkeeping Field', compute='_compute_fhe_is_technical',
        search='_search_fhe_is_technical',
        help="Technical column kept by Odoo on every model (creation and write "
             "stamps, identifier, display name). Hidden from the editor by default.")
    fhe_lang_name = fields.Char(
        string='Editing Language', compute='_compute_fhe_lang_name',
        help="Language the label and the tooltip shown here belong to. It is "
             "the language of your own user session; the other languages keep "
             "their own values.")

    # ------------------------------------------------------------------
    # computes / searches
    # ------------------------------------------------------------------
    @api.depends('fhe_customization_ids')
    def _compute_fhe_customized(self):
        for field in self:
            field.fhe_customized = bool(field.fhe_customization_ids)

    def _search_fhe_customized(self, operator, value):
        return _bool_domain(
            _wanted_values(operator, value),
            [('fhe_customization_ids', '!=', False)],
            [('fhe_customization_ids', '=', False)],
        )

    @api.depends('name')
    def _compute_fhe_is_technical(self):
        for field in self:
            name = field.name or ''
            field.fhe_is_technical = name in BOOKKEEPING_FIELDS or name.startswith('_')

    def _search_fhe_is_technical(self, operator, value):
        # '\_%' is a LIKE pattern with an escaped underscore: names that really
        # start with an underscore, not names that contain one.
        return _bool_domain(
            _wanted_values(operator, value),
            ['|', ('name', 'in', list(BOOKKEEPING_FIELDS)), ('name', '=like', '\\_%')],
            ['&', ('name', 'not in', list(BOOKKEEPING_FIELDS)), '!', ('name', '=like', '\\_%')],
        )

    @api.depends_context('lang')
    def _compute_fhe_lang_name(self):
        code = self._fhe_lang()
        lang = self.env['res.lang'].with_context(active_test=False).search(
            [('code', '=', code)], limit=1)
        name = lang.name or code
        for field in self:
            field.fhe_lang_name = name

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @api.model
    def _fhe_lang(self):
        """Language the ORM will read and write translatable values in."""
        return self.env.context.get('lang') or 'en_US'

    def _fhe_clear_caches(self):
        """Field labels and tooltips are served from an ORM cache.

        Called once per user action, never per record: emptying the caches
        signals every worker of the database.
        """
        registry = self.env.registry
        # 19.0 keeps the label caches in a separate bucket that the narrower
        # clear_cache() does not touch, so clear everything where available.
        if hasattr(registry, 'clear_all_caches'):
            registry.clear_all_caches()
        elif hasattr(registry, 'clear_caches'):
            registry.clear_caches()
        else:  # pragma: no cover - older API
            self.clear_caches()

    @api.model
    def _fhe_assert_model_accessible(self, model_name):
        """Refuse to relabel a field of a model the user may not read."""
        if not model_name or model_name not in self.env:
            raise UserError(
                _("Model '%s' is not installed in this database, so the labels of "
                  "its fields cannot be edited.") % (model_name,))
        model = self.env[model_name]
        if model._abstract:
            raise UserError(
                _("'%s' is an abstract model: it stores nothing and its labels are "
                  "never displayed. Edit the field on the model that uses it.") % (model_name,))
        if hasattr(model, 'check_access'):
            model.check_access('read')
        else:  # pragma: no cover - older API
            model.check_access_rights('read')

    def _fhe_check_customization_allowed(self):
        """Only Settings administrators, and only on models they may read.

        Every entry point calls this *before* touching anything.
        """
        if self.env.su:
            return
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(
                _("Only Settings administrators can change field labels and tooltips."))
        if hasattr(self, 'check_access'):
            self.check_access('write')
        else:  # pragma: no cover - older API
            self.check_access_rights('write')
            self.check_access_rule('write')
        for model_name in set(self.mapped('model')):
            self._fhe_assert_model_accessible(model_name)

    def _fhe_capture_originals(self):
        """Remember the values a field had before its first customization."""
        lang = self._fhe_lang()
        Customization = self.env['field.help.customization']
        known = Customization._fhe_for_fields(self.ids, lang).mapped('field_id').ids
        missing = [field for field in self if field.id not in known]
        if missing:
            Customization.create([{
                'field_id': field.id,
                'lang': lang,
                'original_description': field.field_description,
                'original_help': field.help,
                'custom_description': field.field_description,
                'custom_help': field.help,
            } for field in missing])

    def _fhe_sync_customizations(self, applied):
        """Record what is applied now, and drop entries back to the original."""
        lang = self._fhe_lang()
        mapping = {'field_description': 'custom_description', 'help': 'custom_help'}
        values = {mapping[key]: applied[key] for key in mapping if key in applied}
        customizations = self.env['field.help.customization']._fhe_for_fields(self.ids, lang)
        if values:
            customizations.write(values)
        customizations.filtered(
            lambda customization:
                (customization.custom_description or '') == (customization.original_description or '')
                and (customization.custom_help or '') == (customization.original_help or '')
        ).unlink()

    def _fhe_void_override(self, keys, lang):
        """Remove the entries that override what the field ships with."""
        names = ['ir.model.fields,%s' % (key,) for key in keys]
        self.env['ir.translation'].search([
            ('type', '=', 'model'), ('name', 'in', names),
            ('res_id', 'in', self.ids), ('lang', '=', lang),
        ]).unlink()

    def _fhe_apply_label_values(self, values):
        """Store the customization as a model translation of the edited language.

        On this Odoo series the properties of a base field cannot be written
        (`Properties of base fields cannot be altered in this manner!`), so a
        label or a tooltip is customized the way Settings / Translations does
        it: with an `ir.translation` entry for the language being edited. The
        value shipped by Odoo stays untouched in the table, which is what makes
        a reset exact - and what keeps the other languages out of harm's way.
        """
        lang = self._fhe_lang()
        truthy = {key: value for key, value in values.items() if value}
        empty = [key for key, value in values.items() if not value]
        if 'field_description' in empty:
            raise UserError(_("A field must keep a label; only the tooltip can be emptied."))
        if empty:
            # nothing to override any more: the field falls back to what it ships
            self._fhe_void_override(empty, lang)
        if not truthy:
            return
        translations = self.env['ir.translation']
        sources = {
            record.id: {key: record[key] for key in truthy}
            for record in self.with_context(lang=None)
        }
        for key, value in truthy.items():
            name = 'ir.model.fields,%s' % (key,)
            existing = translations.search([
                ('type', '=', 'model'), ('name', '=', name),
                ('res_id', 'in', self.ids), ('lang', '=', lang),
            ])
            by_field = {entry.res_id: entry for entry in existing}
            to_create = []
            for field in self:
                source = sources[field.id][key] or ''
                entry = by_field.get(field.id)
                if entry:
                    entry.write({'value': value, 'src': source, 'state': 'translated'})
                else:
                    to_create.append({
                        'type': 'model', 'name': name, 'res_id': field.id,
                        'lang': lang, 'src': source, 'value': value,
                        'state': 'translated',
                    })
            if to_create:
                translations.create(to_create)

    def _fhe_apply_values(self, values, lang):
        """Apply values without recording them as a new customization."""
        records = self.with_context(lang=lang)
        records._fhe_check_customization_allowed()
        records._fhe_apply_label_values(values)

    def _fhe_restore_original(self, customization):
        """Put back exactly what the field shipped with, for one language."""
        self.ensure_one()
        self._fhe_check_customization_allowed()
        lang = customization.lang
        source = self.with_context(lang=None)
        values = {}
        void = []
        for key, original in (('field_description', customization.original_description),
                              ('help', customization.original_help)):
            if (source[key] or '') == (original or ''):
                # the value the field ships with already is the original:
                # removing the override is the exact way back
                void.append(key)
            else:
                values[key] = original
        if void:
            self._fhe_void_override(void, lang)
        if values:
            self._fhe_apply_values(values, lang)

    # ------------------------------------------------------------------
    # write
    # ------------------------------------------------------------------
    def write(self, vals):
        applied = {key: vals[key] for key in LABEL_KEYS if key in vals}
        # Module installation and upgrade reflect labels straight into the
        # table; only user-initiated changes are customizations.
        if (not applied or not self.env.registry.ready
                or getattr(_reentrancy, 'active', False)):
            return super().write(vals)
        self._fhe_check_customization_allowed()
        self._fhe_capture_originals()
        remaining = {key: value for key, value in vals.items() if key not in applied}
        result = super().write(remaining) if remaining else True
        self._fhe_apply_label_values(applied)
        self._fhe_sync_customizations(applied)
        self._fhe_clear_caches()
        return result

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def action_fhe_reset(self):
        """Restore the original label and tooltip of the selected fields."""
        self._fhe_check_customization_allowed()
        self.mapped('fhe_customization_ids').action_reset()
        return True

    def action_fhe_open(self):
        """Open this field in the label editor form."""
        self.ensure_one()
        view = self.env.ref('field_help_editor.view_fhe_field_form')
        return {
            'type': 'ir.actions.act_window',
            'name': self.field_description or self.name,
            'res_model': 'ir.model.fields',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'target': 'current',
        }

    def action_fhe_reapply(self):
        """Apply the recorded customizations again."""
        self._fhe_check_customization_allowed()
        self.mapped('fhe_customization_ids').action_reapply()
        return True
