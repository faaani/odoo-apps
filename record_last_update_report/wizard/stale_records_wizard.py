# -*- coding: utf-8 -*-
# Part of record_last_update_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import inspect
import logging
from ast import literal_eval
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

# Cumulative age buckets, in days: "older than 30" deliberately contains
# "older than 365" as well, which is what people mean when they ask how much of
# a table is stale. The UI says so instead of leaving it to be guessed.
AGE_BUCKETS = (30, 90, 180, 365)
# Rows listed in the sample. The counts always cover every matching record; only
# this list is capped, and the result says by how much it was truncated.
DEFAULT_SAMPLE_LINES = 50
MAX_SAMPLE_LINES = 500
# Sanity bound on the age: 200 years of days is not a report, it is a typo.
MAX_AGE_DAYS = 73000

# 17.0 rewrote the internal grouping API as
# _read_group(domain, groupby, aggregates) and 19.0 deprecates the public
# read_group(); resolve once which one this series actually supports.
_READ_GROUP = getattr(models.BaseModel, '_read_group', None)
_MODERN_READ_GROUP = bool(_READ_GROUP) and (
    'aggregates' in inspect.signature(_READ_GROUP).parameters)


def model_is_readable(model):
    """Whether the current user may read ``model`` at all (ACL level)."""
    # 18.0 replaced check_access_rights() with has_access(); the old name still
    # exists there but is deprecated, so prefer the new one when present.
    if hasattr(model, 'has_access'):
        return model.has_access('read')
    return model.check_access_rights('read', raise_exception=False)


class StaleRecordsWizard(models.TransientModel):
    """Read-only staleness report for one model.

    Counts come from aggregate queries and the sample from a single capped
    search, both issued as the current user so that ir.rule record rules apply.
    The model is never browsed record by record and nothing is ever written to
    it: this report only reads.
    """
    _name = 'stale.records.wizard'
    _description = 'Stale Records Report'

    model_id = fields.Many2one(
        'ir.model', string='Model', required=True, ondelete='cascade',
        domain="[('transient', '=', False)]",
        help='The model to analyse, for example Contact, Lead or Product.')
    model_name = fields.Char(
        related='model_id.model', string='Technical Name', readonly=True)
    age_days = fields.Integer(
        string='Not Updated For (Days)', default=90, required=True,
        help='A record counts as stale when its last-update date is older than '
             'this many days. The four age buckets below are always reported as '
             'well, whatever value you use here.')
    extra_domain = fields.Char(
        string='Extra Filter',
        help='Optional Odoo domain narrowing the records to look at, written as '
             'a literal Python list, e.g. [("customer_rank", ">", 0)]. Only '
             'literal values are accepted: expressions such as uid or '
             'context_today() are not evaluated.')
    include_archived = fields.Boolean(
        string='Include Archived Records', default=False,
        help='Off by default, so the report covers the same records as the '
             'ordinary list view of that model.')
    sample_limit = fields.Integer(
        string='Rows to List', default=DEFAULT_SAMPLE_LINES, required=True,
        help='How many of the oldest records to list. Capped at %s rows; the '
             'counts are never capped.' % MAX_SAMPLE_LINES)

    state = fields.Selection(
        [('draft', 'Criteria'), ('done', 'Result')],
        string='Status', default='draft', required=True, readonly=True)
    analyzed_on = fields.Datetime(string='Analysed On', readonly=True)
    scope_count = fields.Integer(
        string='Records in Scope', readonly=True,
        help='Records matching the extra filter, whatever their age.')
    stale_count = fields.Integer(
        string='Stale Records', readonly=True,
        help='Records not updated for at least the number of days requested.')
    # The four buckets are cumulative on purpose: "how much of this table is
    # rotting" is a nested question, and the form says so under the figures.
    count_30 = fields.Integer(
        string='Older Than 30 Days', readonly=True,
        help='Records not updated for at least 30 days. The buckets are '
             'cumulative: this one also contains the older ones.')
    count_90 = fields.Integer(
        string='Older Than 90 Days', readonly=True,
        help='Records not updated for at least 90 days.')
    count_180 = fields.Integer(
        string='Older Than 180 Days', readonly=True,
        help='Records not updated for at least 180 days.')
    count_365 = fields.Integer(
        string='Older Than 365 Days', readonly=True,
        help='Records not updated for at least a year.')
    listed_count = fields.Integer(
        string='Rows Listed', readonly=True,
        help='How many of the stale records are shown in the list below.')
    truncated = fields.Boolean(
        string='List Truncated', readonly=True,
        help='Ticked when more records are stale than the list may show.')
    result_note = fields.Char(string='Result', readonly=True)
    line_ids = fields.One2many(
        'stale.records.line', 'wizard_id', string='Oldest Records', readonly=True)

    def _compute_display_name(self):
        # Every series computes display_name here; without an override the
        # breadcrumb of the report reads "stale.records.wizard,4".
        for wizard in self:
            wizard.display_name = _('Stale Records Report')

    # ------------------------------------------------------------------
    # constraints
    # ------------------------------------------------------------------
    @api.constrains('age_days', 'sample_limit')
    def _check_bounds(self):
        for wizard in self:
            if wizard.age_days < 1:
                raise ValidationError(_(
                    'The age must be at least one day.'))
            if wizard.age_days > MAX_AGE_DAYS:
                raise ValidationError(_(
                    'The age cannot exceed %s days.') % MAX_AGE_DAYS)
            if wizard.sample_limit < 1:
                raise ValidationError(_(
                    'At least one row must be listed.'))
            if wizard.sample_limit > MAX_SAMPLE_LINES:
                raise ValidationError(_(
                    'The list is capped at %s rows: reading more records than '
                    'that in one page is what the counts are for.'
                ) % MAX_SAMPLE_LINES)

    # ------------------------------------------------------------------
    # guards
    # ------------------------------------------------------------------
    def _target_model(self):
        """Return the (empty) target recordset once every guard has passed.

        Each refusal is explicit: a report that quietly returned zero on a model
        it cannot read or cannot age would be read as "nothing is stale".
        """
        self.ensure_one()
        model_name = self.model_id.model
        if not model_name or model_name not in self.env:
            raise UserError(_(
                'The model "%s" does not exist in this database. It probably '
                'belongs to a module that has been uninstalled.'
            ) % (model_name or self.model_id.display_name))
        model = self.env[model_name]
        if not model_is_readable(model):
            raise AccessError(_(
                'You are not allowed to read "%s", so this report cannot be run '
                'on it. Ask an administrator to grant you access to that model, '
                'or pick another one.'
            ) % model._description)
        if model._abstract:
            raise UserError(_(
                '"%s" is an abstract model: it has no table and no records of '
                'its own, so there is nothing to age.'
            ) % model._description)
        if model._transient:
            raise UserError(_(
                '"%s" is a wizard (transient) model. Odoo empties it '
                'automatically, so a staleness report on it would be '
                'meaningless.'
            ) % model._description)
        if 'write_date' not in model._fields:
            raise UserError(_(
                '"%s" does not record when its rows were last written '
                '(log access is disabled on this model), so its records cannot '
                'be aged.'
            ) % model._description)
        if 'write_uid' not in model._fields:
            raise UserError(_(
                '"%s" records when its rows were last written but not by whom, '
                'so this report cannot be produced for it.'
            ) % model._description)
        return model

    def _parse_extra_domain(self):
        """The extra filter as a domain list, or [] when it is empty."""
        self.ensure_one()
        raw = (self.extra_domain or '').strip()
        if not raw:
            return []
        message = _(
            'The extra filter must be a literal Odoo domain, for example '
            '[("customer_rank", ">", 0)].')
        try:
            # literal_eval, not safe_eval: this field never needs to call
            # anything, and a literal domain cannot execute code.
            domain = literal_eval(raw)
        except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
            raise UserError(message)
        if not isinstance(domain, (list, tuple)):
            raise UserError(message)
        domain = list(domain)
        for item in domain:
            if isinstance(item, str):
                if item not in ('&', '|', '!'):
                    raise UserError(message)
            elif not (isinstance(item, (list, tuple)) and len(item) == 3):
                raise UserError(message)
        return domain

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def _stale_domain(self, days, reference, extra=None):
        """Domain selecting records not updated for ``days`` days.

        The cut-off is a string so the domain stays JSON-serialisable: it is
        handed to an act_window as well as to search().
        """
        cutoff = fields.Datetime.to_string(reference - timedelta(days=days))
        if extra is None:
            extra = self._parse_extra_domain()
        # A leaf first, so normalize_domain() inserts the implicit '&' in front
        # of an extra filter that starts with an operator such as '|'.
        return [('write_date', '<', cutoff)] + extra

    @api.model
    def _count_records(self, model, domain):
        """COUNT(*) through the ORM, with the caller's record rules applied."""
        if _MODERN_READ_GROUP:  # 17.0+
            # A group-less _read_group asking for __count is a plain
            # SELECT COUNT(*), record rules included.
            rows = model._read_group(domain, [], ['__count'])
            return rows[0][0] if rows else 0
        # 14.0-16.0 must NOT use read_group() here: it replaces an empty field
        # list with every stored field, so the count would drag a SUM over each
        # numeric column of the table along with it. search_count() is the same
        # COUNT(*) under the same rules, without that trap.
        return model.search_count(domain)

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def action_analyze(self):
        """Count the stale records and list the oldest ones. Reads only."""
        self.ensure_one()
        model = self._target_model()
        # active_test mirrors what the ordinary list view of the model shows.
        scope = model.with_context(active_test=not self.include_archived)
        now = fields.Datetime.now()
        extra = self._parse_extra_domain()
        stale_domain = self._stale_domain(self.age_days, now, extra)
        try:
            # A savepoint keeps a rejected filter (unknown field, wrong value
            # type) from poisoning the whole transaction. Reading the sample is
            # inside it too, so a model that cannot be read produces the message
            # below rather than a raw traceback.
            with self.env.cr.savepoint():
                scope_count = self._count_records(scope, extra)
                bucket_counts = {
                    days: self._count_records(
                        scope, self._stale_domain(days, now, extra))
                    for days in AGE_BUCKETS
                }
                stale_count = (
                    bucket_counts[self.age_days] if self.age_days in bucket_counts
                    else self._count_records(scope, stale_domain))
                records = scope.search(
                    stale_domain, order='write_date ASC, id ASC',
                    limit=self.sample_limit)
                line_commands = self._prepare_lines(records, now)
        except UserError:
            # AccessError and ValidationError both derive from UserError: the
            # module's own refusals must reach the user unchanged.
            raise
        except Exception as error:  # pylint: disable=broad-except
            _logger.info('Stale Records Report: rejected query on %s (%s)',
                         model._name, error)
            raise UserError(_(
                'This report could not be run on "%(model)s":\n%(error)s\n\n'
                'Check the extra filter: every field it names must exist on '
                'that model and the values must have the right type.'
            ) % {'model': model._description, 'error': error})

        self.line_ids = [(5, 0, 0)] + line_commands
        self.write({
            'state': 'done',
            'analyzed_on': now,
            'scope_count': scope_count,
            'stale_count': stale_count,
            'count_30': bucket_counts[30],
            'count_90': bucket_counts[90],
            'count_180': bucket_counts[180],
            'count_365': bucket_counts[365],
            'listed_count': len(records),
            'truncated': stale_count > len(records),
            'result_note': self._result_note(stale_count, scope_count, len(records)),
        })
        return True

    def _prepare_lines(self, records, reference):
        """One (0, 0, vals) tuple per sampled record, oldest first."""
        self.ensure_one()
        model_name = records._name
        names = self._sample_names(records)
        commands = []
        for record in records:
            last_update = record.write_date
            commands.append((0, 0, {
                'res_model': model_name,
                'res_id': record.id,
                'record_name': names.get(record.id) or '%s,%s' % (model_name, record.id),
                'last_update': last_update,
                'last_writer_id': record.write_uid.id if record.write_uid else False,
                'days_since_update': (reference - last_update).days if last_update else 0,
            }))
        return commands

    def _sample_names(self, records):
        """``{id: display_name}`` for the sample, read in one batch.

        display_name is computed code and can fail on a broken record. One bad
        row must not cost the whole sample, so the batch is retried row by row
        - each inside its own savepoint - but only if the batch itself raises.
        """
        try:
            # flush=False: these savepoints only guard reads, and the caller has
            # already flushed everything the queries above needed.
            with self.env.cr.savepoint(flush=False):
                return {record.id: record.display_name for record in records}
        except Exception as error:  # pylint: disable=broad-except
            _logger.info('Stale Records Report: display_name failed on %s (%s), '
                         'falling back to one row at a time',
                         records._name, error)
        names = {}
        for record in records:
            try:
                with self.env.cr.savepoint(flush=False):
                    names[record.id] = record.display_name
            except Exception:  # pylint: disable=broad-except
                names[record.id] = False
        return names

    def _result_note(self, stale_count, scope_count, listed):
        """One honest sentence about what the numbers cover."""
        self.ensure_one()
        note = _(
            '%(stale)s of the %(scope)s records you are allowed to see have not '
            'been updated in %(days)s days.'
        ) % {'stale': stale_count, 'scope': scope_count, 'days': self.age_days}
        if not stale_count:
            return note
        if stale_count > listed:
            return note + ' ' + _(
                'The %(listed)s oldest are listed below (list capped at '
                '%(limit)s rows); the counts cover all %(stale)s.'
            ) % {'listed': listed, 'limit': self.sample_limit, 'stale': stale_count}
        return note + ' ' + _('All of them are listed below.')

    def action_reset(self):
        """Go back to the criteria and drop the previous result."""
        self.ensure_one()
        self.line_ids = [(5, 0, 0)]
        self.write({
            'state': 'draft',
            'analyzed_on': False,
            'scope_count': 0,
            'stale_count': 0,
            'count_30': 0,
            'count_90': 0,
            'count_180': 0,
            'count_365': 0,
            'listed_count': 0,
            'truncated': False,
            'result_note': False,
        })
        return True

    def action_open_records(self):
        """Open every stale record - not just the listed sample - as a list."""
        self.ensure_one()
        model = self._target_model()
        reference = self.analyzed_on or fields.Datetime.now()
        return {
            'type': 'ir.actions.act_window',
            'name': _('%(model)s not updated in %(days)s days') % {
                'model': model._description, 'days': self.age_days},
            'res_model': model._name,
            'domain': self._stale_domain(self.age_days, reference),
            'context': {'active_test': not self.include_archived},
            'view_mode': 'tree,form',
            'target': 'current',
        }


class StaleRecordsLine(models.TransientModel):
    """One sampled record: what it is, when it was last written and by whom."""
    _name = 'stale.records.line'
    _description = 'Stale Record'
    _order = 'last_update asc, res_id asc'

    wizard_id = fields.Many2one(
        'stale.records.wizard', string='Report', required=True,
        ondelete='cascade', index=True)
    res_model = fields.Char(string='Model', readonly=True)
    res_id = fields.Integer(string='Record ID', readonly=True)
    record_name = fields.Char(string='Record', readonly=True)
    last_update = fields.Datetime(string='Last Updated', readonly=True)
    last_writer_id = fields.Many2one(
        'res.users', string='Last Updated By', readonly=True, ondelete='set null',
        help='The user stored on the record as its last writer. Empty when the '
             'row was last written outside the ORM.')
    days_since_update = fields.Integer(
        string='Days Since Update', readonly=True,
        help='Whole days between the last update and the moment the report ran.')

    @api.depends('record_name', 'res_id')
    def _compute_display_name(self):
        for line in self:
            line.display_name = line.record_name or _('Record #%s') % line.res_id

    def action_open_record(self):
        """Open the underlying record in its own form view."""
        self.ensure_one()
        if not self.res_model or self.res_model not in self.env:
            raise UserError(_(
                'The model of this line is no longer installed.'))
        model = self.env[self.res_model]
        # exists() is a raw existence check with no ACL behind it: refuse before
        # probing, so this button can never become a row-existence oracle.
        if not model_is_readable(model):
            raise AccessError(_(
                'You are not allowed to read "%s".') % model._description)
        if not model.browse(self.res_id).exists():
            raise UserError(_(
                'That record has been deleted since the report was run.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
