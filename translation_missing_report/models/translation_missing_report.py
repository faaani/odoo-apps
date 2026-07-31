# -*- coding: utf-8 -*-
# Part of translation_missing_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# The ORM writes the untranslated value of a translated field under this key:
# it is the jsonb source key on 16.0+ and, on 14.0/15.0, the language of the
# value physically stored in the column.
SOURCE_LANG = 'en_US'

# Shown instead of a module name for records that have no external ID (records
# created by users, not shipped by a module).
NO_MODULE = '(user data)'

# Table/column names come from the registry, never from user input, but they
# are interpolated into SQL so they are validated all the same.
IDENTIFIER_RE = re.compile(r'^[a-z_][a-z0-9_]*$')

MAX_TERM_LIMIT = 20000
PREVIEW_LENGTH = 250

KIND_SELECTION = [
    ('menu', 'Menu item'),
    ('field', 'Field label / help'),
    ('selection', 'Selection value'),
    ('model', 'Model name'),
    ('action', 'Action name'),
    ('report', 'Report'),
    ('view', 'View / QWeb template content'),
    ('group', 'Access group'),
    ('code', 'Source code term (Python / JavaScript)'),
    ('data', 'Record content'),
]
KIND_ORDER = {kind: index for index, (kind, _label) in enumerate(KIND_SELECTION)}
# Everything except plain business record content is "user interface".
UI_KINDS = [kind for kind, _label in KIND_SELECTION if kind != 'data']

KIND_BY_MODEL = {
    'ir.ui.menu': 'menu',
    'ir.model.fields': 'field',
    'ir.model.fields.selection': 'selection',
    'ir.model': 'model',
    'ir.ui.view': 'view',
    'ir.actions.report': 'report',
    'res.groups': 'group',
}

REASON_SELECTION = [
    ('missing', 'Not translated'),
    ('identical', 'Same as source'),
]


class TranslationMissingReport(models.TransientModel):
    _name = 'translation.missing.report'
    _description = 'Missing Translations Report'
    _rec_name = 'name'

    name = fields.Char(string='Report', compute='_compute_name')
    lang_id = fields.Many2one(
        'res.lang', string='Language', required=True, ondelete='cascade',
        domain="[('active', '=', True)]",
        default=lambda self: self._tmr_default_lang(),
        help='Installed language to audit. Only activated languages can be '
             'reported on.',
    )
    scope = fields.Selection(
        [
            ('ui', 'User interface only'),
            ('data', 'Business record content only'),
            ('all', 'Everything'),
        ],
        string='Scope', required=True, default='ui',
        help='"User interface only" covers menus, field labels and help, model '
             'names, selection values, action and report names, view / QWeb '
             'template content and access group labels. "Business record '
             'content" covers translatable text stored on ordinary records '
             '(product names, country names, ...).',
    )
    include_identical = fields.Boolean(
        string='Report terms identical to the source', default=False,
        help='A translation that is character for character the same as the '
             'source term is usually a term nobody has looked at yet. Tick this '
             'to list those terms as well. Words that are genuinely the same in '
             'both languages will show up too.',
    )
    term_limit = fields.Integer(
        string='Listed Terms Limit', default=500, required=True,
        help='Maximum number of individual terms listed. Counts per module are '
             'always computed over the whole database; only the list of terms '
             'is capped, and the report says so when it is.',
    )
    storage_mode = fields.Selection(
        [
            ('ir_translation', 'ir.translation table (Odoo 14.0 / 15.0)'),
            ('jsonb', 'JSONB columns on the records (Odoo 16.0 and later)'),
        ],
        string='Translation Storage', readonly=True,
        default=lambda self: self._tmr_storage_mode(),
        help='Where this Odoo version keeps translations. The report reads '
             'whichever storage the running version uses.',
    )
    coverage_note = fields.Text(
        string='What This Version Can Report', readonly=True,
        default=lambda self: self._tmr_coverage_note(),
    )
    result_note = fields.Text(string='Result', readonly=True)
    term_total = fields.Integer(string='Reported Terms', readonly=True)
    term_listed = fields.Integer(string='Listed Terms', readonly=True)
    module_count = fields.Integer(string='Modules Concerned', readonly=True)
    truncated = fields.Boolean(string='List Truncated', readonly=True)
    summary_ids = fields.One2many(
        'translation.missing.summary', 'report_id', string='Per Module',
        readonly=True,
    )
    line_ids = fields.One2many(
        'translation.missing.line', 'report_id', string='Terms', readonly=True,
    )

    @api.depends('lang_id')
    def _compute_name(self):
        for report in self:
            if report.lang_id:
                report.name = _('Missing translations in %s') % (report.lang_id.name,)
            else:
                report.name = _('Missing Translations Report')

    # ------------------------------------------------------------------
    # storage detection
    # ------------------------------------------------------------------
    @api.model
    def _tmr_storage_mode(self):
        """Return the translation storage used by the running Odoo series.

        14.0 and 15.0 keep every translated term as a row of ``ir.translation``.
        16.0 dropped that model and moved translations into jsonb columns on the
        records themselves. The model is the runtime marker, not the version
        number: it is checked in the registry so the same code works on both.
        """
        return 'ir_translation' if 'ir.translation' in self.env else 'jsonb'

    @api.model
    def _tmr_default_lang(self):
        """First installed language that is not the source one, if any."""
        return self.env['res.lang'].search(
            [('code', '!=', SOURCE_LANG)], limit=1, order='name')

    @api.model
    def _tmr_coverage_note(self):
        """Plain-language description of what this series can and cannot see."""
        common = _(
            'Scanned: every stored translatable column of every installed '
            'model - menus, field labels and help, model names, selection '
            'values, action and report names, view / QWeb template content, '
            'access group labels and translatable record content.'
        )
        if self._tmr_storage_mode() == 'jsonb':
            specific = _(
                'This Odoo version stores translations in jsonb columns on the '
                'records themselves; the ir.translation model no longer exists. '
                'Two consequences, and they are real limitations:\n'
                '- Terms that live only in Python or JavaScript source code are '
                'not stored in the database on this version (they are read from '
                'the module .po files at runtime), so this report cannot list '
                'them. On 14.0 / 15.0 the same report does list them.\n'
                '- Structured fields (view architectures, HTML fields) are '
                'stored as one jsonb value per language, so they are reported '
                'per record and field with a preview of the source, not term by '
                'term.'
            )
        else:
            specific = _(
                'This Odoo version stores translations as rows of the '
                'ir.translation table. In addition to the stored record terms, '
                'this report also lists untranslated Python / JavaScript source '
                'terms (ir.translation rows of type "code"), which the 16.0+ '
                'jsonb storage cannot offer at all.\n'
                'Structured fields (view architectures, HTML fields) are '
                'reported per record and field: such a record counts as '
                'translated as soon as one of its terms has been translated.'
            )
        limits = _(
            'Counts per module are computed database-wide with grouped SQL. '
            'The listed terms are additionally filtered through the standard '
            'access rules of each model, so a record you are not allowed to '
            'read is counted but never displayed. Nothing is ever written: the '
            'report never creates, changes or deletes a translation.'
        )
        return '%s\n\n%s\n\n%s' % (common, specific, limits)

    # ------------------------------------------------------------------
    # scan targets
    # ------------------------------------------------------------------
    @api.model
    def _tmr_flush(self):
        """Push pending ORM writes to the tables before reading them in SQL."""
        if hasattr(self.env, 'flush_all'):
            self.env.flush_all()          # 16.0+
        else:
            self.env['base'].flush()      # 14.0 / 15.0: flushes every model

    @api.model
    def _tmr_kind(self, model_name):
        if model_name in KIND_BY_MODEL:
            return KIND_BY_MODEL[model_name]
        if model_name.startswith('ir.actions.'):
            return 'action'
        return 'data'

    @api.model
    def _tmr_targets(self, scope):
        """One entry per translatable stored column, deduplicated by table.

        Several models can share a table (``ir.actions.actions`` and
        ``ir.actions.act_window_close`` both live in ``ir_actions``); scanning
        the table once per model would count the same term twice.
        """
        self.env.cr.execute("""
            SELECT table_name, column_name
              FROM information_schema.columns
             WHERE table_schema = current_schema()
        """)
        existing_columns = set(self.env.cr.fetchall())

        by_column = {}
        for model_name in self.env.registry:
            Model = self.env[model_name]
            if Model._abstract or Model._transient or not Model._auto:
                continue
            table = Model._table
            if not IDENTIFIER_RE.match(table):
                continue
            for field_name, field in Model._fields.items():
                if not field.translate or not field.store:
                    continue
                if getattr(field, 'inherited', False):
                    continue
                if not IDENTIFIER_RE.match(field_name):
                    continue
                if (table, field_name) not in existing_columns:
                    continue
                by_column.setdefault((table, field_name), set()).add(model_name)

        targets = []
        for (table, column), model_names in by_column.items():
            # shortest name = the base model of the table, e.g. ir.actions.actions
            primary = min(model_names, key=lambda name: (len(name), name))
            kind = self._tmr_kind(primary)
            if scope == 'ui' and kind not in UI_KINDS:
                continue
            if scope == 'data' and kind != 'data':
                continue
            targets.append({
                'table': table,
                'column': column,
                'model': primary,
                'models': sorted(model_names),
                'kind': kind,
            })
        targets.sort(key=lambda t: (KIND_ORDER.get(t['kind'], 99), t['model'], t['column']))
        return targets

    # ------------------------------------------------------------------
    # SQL per storage model
    # ------------------------------------------------------------------
    @api.model
    def _tmr_sql_fragments(self, target):
        """SQL pieces for one column, written for the storage of this series.

        Returns (from_clause, missing_expr, identical_expr, source_expr,
        has_source_expr). The named parameters ``lang``, ``source``, ``models``
        and - on 14.0/15.0 - ``names`` are bound by :meth:`_tmr_sql_params`.
        """
        table = '"%s"' % target['table']
        column = 't."%s"' % target['column']
        module_join = """
            LEFT JOIN (SELECT DISTINCT ON (res_id) res_id, module
                         FROM ir_model_data
                        WHERE model = ANY(%(models)s)
                     ORDER BY res_id, id) d ON d.res_id = t.id
        """
        if self._tmr_storage_mode() == 'jsonb':
            from_clause = '%s t %s' % (table, module_join)
            missing = "%s->>%%(lang)s IS NULL" % column
            identical = ("%s->>%%(lang)s IS NOT NULL AND %s->>%%(lang)s = %s->>%%(source)s"
                         % (column, column, column))
            source_expr = "LEFT(%s->>%%(source)s, %d)" % (column, PREVIEW_LENGTH)
            has_source = "%s IS NOT NULL AND COALESCE(%s->>%%(source)s, '') <> ''" % (column, column)
        else:
            translation_join = """
                LEFT JOIN (SELECT res_id,
                                  bool_or(value IS NOT NULL AND value <> '') AS has_value,
                                  bool_or(value IS NOT NULL AND value <> ''
                                          AND value IS DISTINCT FROM src) AS has_diff
                             FROM ir_translation
                            WHERE lang = %(lang)s
                              AND type IN ('model', 'model_terms')
                              AND name = ANY(%(names)s)
                              AND res_id IS NOT NULL
                         GROUP BY res_id) tr ON tr.res_id = t.id
            """
            from_clause = '%s t %s %s' % (table, translation_join, module_join)
            missing = "NOT COALESCE(tr.has_value, FALSE)"
            identical = "COALESCE(tr.has_value, FALSE) AND NOT COALESCE(tr.has_diff, FALSE)"
            source_expr = "LEFT(%s, %d)" % (column, PREVIEW_LENGTH)
            has_source = "%s IS NOT NULL AND %s <> ''" % (column, column)
        return from_clause, missing, identical, source_expr, has_source

    @api.model
    def _tmr_sql_params(self, target, lang_code):
        params = {
            'lang': lang_code,
            'source': SOURCE_LANG,
            'models': target['models'],
        }
        if self._tmr_storage_mode() == 'ir_translation':
            params['names'] = ['%s,%s' % (model, target['column']) for model in target['models']]
        return params

    # ------------------------------------------------------------------
    # scan
    # ------------------------------------------------------------------
    @api.model
    def _tmr_count_target(self, target, lang_code):
        """Grouped count for one column: {module: (scanned, missing, identical)}."""
        from_clause, missing, identical, _source, has_source = self._tmr_sql_fragments(target)
        query = """
            SELECT COALESCE(d.module, '') AS module,
                   COUNT(*) AS scanned,
                   COUNT(*) FILTER (WHERE {missing}) AS missing,
                   COUNT(*) FILTER (WHERE {identical}) AS identical
              FROM {from_clause}
             WHERE {has_source}
          GROUP BY 1
        """.format(from_clause=from_clause, missing=missing,
                   identical=identical, has_source=has_source)
        self.env.cr.execute(query, self._tmr_sql_params(target, lang_code))
        return {row[0]: (row[1], row[2], row[3]) for row in self.env.cr.fetchall()}

    @api.model
    def _tmr_fetch_terms(self, target, lang_code, include_identical, limit):
        """Up to `limit` reported terms of one column, access-rule filtered."""
        from_clause, missing, identical, source_expr, has_source = self._tmr_sql_fragments(target)
        if include_identical:
            reported = '((%s) OR (%s))' % (missing, identical)
        else:
            reported = '(%s)' % (missing,)
        query = """
            SELECT t.id,
                   COALESCE(d.module, '') AS module,
                   CASE WHEN {missing} THEN 'missing' ELSE 'identical' END AS reason,
                   {source_expr} AS source_term
              FROM {from_clause}
             WHERE {has_source} AND {reported}
          ORDER BY t.id
             LIMIT {limit}
        """.format(from_clause=from_clause, missing=missing, source_expr=source_expr,
                   has_source=has_source, reported=reported, limit=int(limit))
        self.env.cr.execute(query, self._tmr_sql_params(target, lang_code))
        rows = self.env.cr.fetchall()
        if not rows:
            return [], 0
        # Never display a record the user is not allowed to read: the counts
        # above are database-wide, the listing goes through the access rules.
        records = self.env[target['model']].browse([row[0] for row in rows])
        allowed = set(self._tmr_readable(records).ids)
        vals_list = []
        for res_id, module, reason, source_term in rows:
            if res_id not in allowed:
                continue
            vals_list.append({
                'module': module or NO_MODULE,
                'kind': target['kind'],
                'source_ref': '%s,%s' % (target['model'], target['column']),
                'res_id': res_id,
                'source_term': source_term or '',
                'reason': reason,
            })
        return vals_list, len(rows) - len(vals_list)

    @api.model
    def _tmr_readable(self, records):
        """Subset of `records` the current user may read (ACL + record rules).

        18.0 replaced check_access_rights/_filter_access_rules with a single
        _filtered_access(); both APIs are used here so the same code runs on
        14.0 through 19.0.
        """
        if hasattr(records, '_filtered_access'):
            return records._filtered_access('read')
        if not records.check_access_rights('read', raise_exception=False):
            _logger.info('translation_missing_report: no read access on %s, '
                         'its terms are counted but not listed', records._name)
            return records.browse()
        return records._filter_access_rules('read')

    @api.model
    def _tmr_count_code_terms(self, lang_code):
        """ir.translation rows of type 'code' - 14.0/15.0 only."""
        self.env.cr.execute("""
            SELECT COALESCE(module, '') AS module,
                   COUNT(*) AS scanned,
                   COUNT(*) FILTER (WHERE value IS NULL OR value = '') AS missing,
                   COUNT(*) FILTER (WHERE value IS NOT NULL AND value <> ''
                                      AND value = src) AS identical
              FROM ir_translation
             WHERE lang = %(lang)s AND type = 'code' AND COALESCE(src, '') <> ''
          GROUP BY 1
        """, {'lang': lang_code})
        return {row[0]: (row[1], row[2], row[3]) for row in self.env.cr.fetchall()}

    @api.model
    def _tmr_fetch_code_terms(self, lang_code, include_identical, limit):
        missing = "(value IS NULL OR value = '')"
        identical = "(value IS NOT NULL AND value <> '' AND value = src)"
        reported = '(%s OR %s)' % (missing, identical) if include_identical else missing
        self.env.cr.execute("""
            SELECT id, COALESCE(module, '') AS module,
                   CASE WHEN {missing} THEN 'missing' ELSE 'identical' END AS reason,
                   LEFT(src, {preview}) AS source_term,
                   name
              FROM ir_translation
             WHERE lang = %(lang)s AND type = 'code' AND COALESCE(src, '') <> ''
               AND {reported}
          ORDER BY id
             LIMIT {limit}
        """.format(missing=missing, reported=reported, preview=PREVIEW_LENGTH,
                   limit=int(limit)), {'lang': lang_code})
        return [{
            'module': row[1] or NO_MODULE,
            'kind': 'code',
            'source_ref': row[4] or '',
            'res_id': 0,
            'source_term': row[3] or '',
            'reason': row[2],
        } for row in self.env.cr.fetchall()]

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def _tmr_check_language(self):
        self.ensure_one()
        lang = self.lang_id
        if not lang:
            raise UserError(_('Select the language to report on.'))
        if not lang.active:
            raise UserError(_(
                'The language %s (%s) is not installed in this database, so '
                'there is nothing to report on it. Install it first from '
                'Settings > Translations > Languages, then run this report '
                'again.'
            ) % (lang.name, lang.code))
        if lang.code == SOURCE_LANG:
            raise UserError(_(
                '%s is the source language of this database: its terms are the '
                'terms other languages are translated from, so it can never be '
                '"missing a translation". Pick another installed language.'
            ) % (lang.code,))
        if self.term_limit < 1 or self.term_limit > MAX_TERM_LIMIT:
            raise UserError(_(
                'The listed terms limit must be between 1 and %s.'
            ) % (MAX_TERM_LIMIT,))
        return lang

    def action_generate(self):
        self.ensure_one()
        lang = self._tmr_check_language()
        # Read access on the report implies read access on its own lines; the
        # scan itself is admin-only through security/ir.model.access.csv.
        self.line_ids.unlink()
        self.summary_ids.unlink()
        self._tmr_flush()

        counters = {}
        per_target = []
        targets = self._tmr_targets(self.scope)
        for target in targets:
            try:
                with self.env.cr.savepoint():
                    counts = self._tmr_count_target(target, lang.code)
            except Exception:
                # A single unreadable column must not abort the whole report.
                _logger.warning(
                    'translation_missing_report: skipped %s.%s',
                    target['table'], target['column'], exc_info=True)
                continue
            reported_here = 0
            for module, (scanned, missing, identical) in counts.items():
                key = (module or NO_MODULE, target['kind'])
                previous = counters.get(key, (0, 0, 0))
                counters[key] = (previous[0] + scanned, previous[1] + missing,
                                 previous[2] + identical)
                reported_here += missing + (identical if self.include_identical else 0)
            if reported_here:
                per_target.append((target, reported_here))

        code_terms_available = self._tmr_storage_mode() == 'ir_translation'
        code_reported = 0
        if code_terms_available and self.scope in ('ui', 'all'):
            try:
                with self.env.cr.savepoint():
                    code_counts = self._tmr_count_code_terms(lang.code)
            except Exception:
                _logger.warning('translation_missing_report: code terms skipped',
                                exc_info=True)
                code_counts = {}
            for module, (scanned, missing, identical) in code_counts.items():
                key = (module or NO_MODULE, 'code')
                previous = counters.get(key, (0, 0, 0))
                counters[key] = (previous[0] + scanned, previous[1] + missing,
                                 previous[2] + identical)
                code_reported += missing + (identical if self.include_identical else 0)

        summary_vals = []
        term_total = 0
        for (module, kind), (scanned, missing, identical) in counters.items():
            reported = missing + (identical if self.include_identical else 0)
            if not reported:
                continue
            term_total += reported
            summary_vals.append({
                'report_id': self.id,
                'module': module,
                'kind': kind,
                'scanned_count': scanned,
                'missing_count': missing,
                'identical_count': identical,
                'reported_count': reported,
            })
        summary_vals.sort(key=lambda vals: (-vals['reported_count'], vals['module'],
                                            KIND_ORDER.get(vals['kind'], 99)))
        self.env['translation.missing.summary'].create(summary_vals)

        line_vals = []
        hidden = 0
        remaining = self.term_limit
        if code_reported and remaining > 0:
            code_vals = self._tmr_fetch_code_terms(
                lang.code, self.include_identical, remaining)
            for vals in code_vals:
                vals['report_id'] = self.id
            line_vals.extend(code_vals)
            remaining -= len(code_vals)
        for target, _reported_here in per_target:
            if remaining <= 0:
                break
            try:
                with self.env.cr.savepoint():
                    vals_list, skipped = self._tmr_fetch_terms(
                        target, lang.code, self.include_identical, remaining)
            except Exception:
                _logger.warning(
                    'translation_missing_report: listing skipped for %s.%s',
                    target['table'], target['column'], exc_info=True)
                continue
            hidden += skipped
            for vals in vals_list:
                vals['report_id'] = self.id
            line_vals.extend(vals_list)
            remaining -= len(vals_list) + skipped
        self.env['translation.missing.line'].create(line_vals)

        self.term_total = term_total
        self.term_listed = len(line_vals)
        self.module_count = len({vals['module'] for vals in summary_vals})
        self.truncated = term_total > len(line_vals)
        self.result_note = self._tmr_build_note(lang, term_total, len(line_vals), hidden)
        return self._tmr_result_action()

    def _tmr_build_note(self, lang, term_total, listed, hidden):
        self.ensure_one()
        if not term_total:
            return _(
                'Nothing to report: every scanned term has a translation in %s '
                '(%s) for the selected scope.'
            ) % (lang.name, lang.code)
        parts = [_(
            '%(total)s term(s) still need attention in %(language)s (%(code)s), '
            'spread over %(modules)s module(s).'
        ) % {
            'total': term_total,
            'language': lang.name,
            'code': lang.code,
            'modules': self.module_count,
        }]
        if self.truncated:
            parts.append(_(
                'Only the first %(listed)s of them are listed below (limit: '
                '%(limit)s terms). The per-module counts cover all of them - '
                'raise the limit or narrow the scope to list more.'
            ) % {'listed': listed, 'limit': self.term_limit})
        else:
            parts.append(_('All of them are listed below.'))
        if hidden:
            parts.append(_(
                '%s term(s) belong to records your access rules do not let you '
                'read: they are counted but not listed.'
            ) % (hidden,))
        if not self.include_identical:
            parts.append(_(
                'Terms whose translation is identical to the source are counted '
                'in the "Same As Source" column but not listed - tick the '
                'option to list them too.'
            ))
        return ' '.join(parts)

    def _tmr_result_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Missing Translations'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref(
                'translation_missing_report.view_translation_missing_report_result').id,
                'form')],
            'target': 'current',
        }

    def action_open_terms(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'translation_missing_report.action_translation_missing_line')
        action['domain'] = [('report_id', '=', self.id)]
        action['context'] = {'search_default_group_module': 1}
        action['target'] = 'current'
        return action

    def action_new_report(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Missing Translations Report'),
            'res_model': self._name,
            'view_mode': 'form',
            'views': [(self.env.ref(
                'translation_missing_report.view_translation_missing_report_form').id,
                'form')],
            'target': 'new',
        }


class TranslationMissingSummary(models.TransientModel):
    _name = 'translation.missing.summary'
    _description = 'Missing Translations: Count Per Module'
    _order = 'reported_count desc, module, kind'

    report_id = fields.Many2one(
        'translation.missing.report', string='Report', required=True,
        ondelete='cascade', index=True,
    )
    module = fields.Char(
        string='Module', required=True,
        help='Technical name of the module the record belongs to, taken from '
             'its external ID. Records created in this database by users have '
             'no module and are grouped under "%s".' % NO_MODULE,
    )
    kind = fields.Selection(KIND_SELECTION, string='Kind', required=True)
    scanned_count = fields.Integer(
        string='Terms Scanned',
        help='Total number of source terms of this kind in this module.',
    )
    missing_count = fields.Integer(string='Not Translated')
    identical_count = fields.Integer(
        string='Same As Source',
        help='Translated with a value identical to the source term. Counted '
             'here for information; listed as terms only when the report option '
             '"Report terms identical to the source" is ticked.',
    )
    reported_count = fields.Integer(
        string='Reported Terms',
        help='Terms this report is listing for this module and kind: the '
             'untranslated ones, plus the identical ones when that option is on.',
    )
    coverage_rate = fields.Float(
        string='Translated %', digits=(5, 1), compute='_compute_coverage_rate',
        help='Percentage of the scanned terms that have a translation '
             'different from the source term.',
    )

    @api.depends('scanned_count', 'missing_count', 'identical_count')
    def _compute_coverage_rate(self):
        for summary in self:
            scanned = summary.scanned_count
            done = scanned - summary.missing_count - summary.identical_count
            summary.coverage_rate = (100.0 * done / scanned) if scanned else 0.0


class TranslationMissingLine(models.TransientModel):
    _name = 'translation.missing.line'
    _description = 'Missing Translations: Term'
    _order = 'module, kind, source_ref, res_id'
    _rec_name = 'source_term'

    report_id = fields.Many2one(
        'translation.missing.report', string='Report', required=True,
        ondelete='cascade', index=True,
    )
    module = fields.Char(string='Module', required=True)
    kind = fields.Selection(KIND_SELECTION, string='Kind', required=True)
    source_ref = fields.Char(
        string='Source',
        help='Where the term comes from: "model,field" for a term stored on a '
             'record, or the source file for a Python / JavaScript term.',
    )
    res_id = fields.Integer(
        string='Record ID',
        help='Database ID of the record carrying the term. 0 for source code '
             'terms, which belong to no record.',
    )
    source_term = fields.Text(
        string='Source Term',
        help='The untranslated text, truncated to %s characters.' % PREVIEW_LENGTH,
    )
    reason = fields.Selection(REASON_SELECTION, string='Status', required=True)
