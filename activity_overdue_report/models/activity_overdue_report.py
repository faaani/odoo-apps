# -*- coding: utf-8 -*-
# Part of activity_overdue_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
from collections import defaultdict

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Ceiling on the number of candidate rows the per-document visibility check will
# examine for a single query. The check has to look at every candidate row (a
# document's record rules cannot be expressed in SQL from here), so an unbounded
# scan on a database with a huge activity backlog would be a denial of service.
# Beyond this ceiling the check keeps the first rows and drops the rest, so row
# lists, record counts, group totals and pivot measures can all come out LOWER
# than reality - never higher - and a warning is logged. The read() path chunks
# instead of truncating: there, a dropped id would mean a wrong "access denied"
# rather than a merely shorter answer. Documented in README.md and index.html.
ACCESS_SCAN_LIMIT = 20000

# One row per open activity. Everything below is a plain column of mail_activity,
# so filtering, sorting and grouping all happen in the database.
#
# days_overdue / urgency are evaluated by PostgreSQL at query time against the
# current UTC date, which is what fields.Date.today() returns on the Python side.
REPORT_VIEW_SQL = """
    SELECT a.id                                     AS id,
           a.user_id                                AS user_id,
           a.activity_type_id                       AS activity_type_id,
           a.summary                                AS summary,
           a.res_model                              AS res_model,
           a.res_model_id                           AS res_model_id,
           a.res_id                                 AS res_id,
           a.res_name                               AS res_name,
           a.date_deadline                          AS date_deadline,
           a.create_uid                             AS creator_id,
           a.create_date                            AS activity_create_date,
           1                                        AS activity_count,
           GREATEST(0, ((now() AT TIME ZONE 'UTC')::date - a.date_deadline))::integer
                                                    AS days_overdue,
           CASE
               WHEN a.date_deadline < (now() AT TIME ZONE 'UTC')::date THEN 'overdue'
               WHEN a.date_deadline = (now() AT TIME ZONE 'UTC')::date THEN 'today'
               ELSE 'planned'
           END                                      AS urgency
      FROM mail_activity a
     WHERE a.date_deadline IS NOT NULL
       AND a.active = TRUE
"""


class ActivityOverdueReport(models.Model):
    """Read-only, cross-model view of the activities that are still open.

    Activities that were marked done or cancelled are gone from this report by
    construction: Odoo deletes a cancelled/done activity, and the versions that
    keep a done activity archive it (active = FALSE), which the SQL view filters
    out. The module never writes to mail.activity or to any document.
    """
    _name = 'activity.overdue.report'
    _description = 'Overdue Activities Report'
    _auto = False
    _rec_name = 'res_name'
    _order = 'date_deadline ASC, id ASC'

    user_id = fields.Many2one(
        'res.users', string='Assigned To', readonly=True,
        help='User the activity is assigned to.',
    )
    activity_type_id = fields.Many2one(
        'mail.activity.type', string='Activity Type', readonly=True,
    )
    summary = fields.Char(
        string='Summary', readonly=True,
        help='Summary typed on the activity, if any.',
    )
    res_model = fields.Char(
        string='Model', readonly=True,
        help='Technical name of the model the activity is attached to.',
    )
    res_model_id = fields.Many2one(
        'ir.model', string='Document Model', readonly=True,
        help='Model the activity is attached to. Group by this field to see '
             'which part of the business is late.',
    )
    res_id = fields.Integer(
        string='Document ID', readonly=True, aggregator=False,
        help='Database id of the document the activity is attached to.',
    )
    res_name = fields.Char(
        string='Document Name (recorded)', readonly=True,
        help='Document name as it was stored on the activity when the activity '
             'was created. It is not refreshed when the document is later '
             'renamed - the "Document" column always shows the live name.',
    )
    date_deadline = fields.Date(
        string='Due Date', readonly=True,
        help='Date the activity is due.',
    )
    days_overdue = fields.Integer(
        string='Days Overdue', readonly=True, aggregator='avg',
        help='Whole days between the due date and today (UTC). Zero for '
             'activities due today or later. Aggregates as an average.',
    )
    urgency = fields.Selection(
        [
            ('overdue', 'Overdue'),
            ('today', 'Due Today'),
            ('planned', 'Planned'),
        ],
        string='Status', readonly=True,
    )
    activity_count = fields.Integer(
        string='Activities', readonly=True,
        help='Always 1 - sum it in the pivot or graph view to chart workload.',
    )
    creator_id = fields.Many2one(
        'res.users', string='Scheduled By', readonly=True,
        help='User who scheduled the activity.',
    )
    activity_create_date = fields.Datetime(
        string='Scheduled On', readonly=True,
    )

    # Resolved live, in bulk, at display time - see _compute_document.
    document_name = fields.Char(
        string='Document', compute='_compute_document',
        help='Current display name of the document the activity is attached to.',
    )
    # Computed on its own, deliberately: assigning a Reference value makes the
    # ORM re-read the model selection and re-check the target row, so this field
    # is only paid for when it is actually displayed (the form view), never for
    # every line of the list.
    document_ref = fields.Reference(
        selection='_selection_document_model', string='Open Document',
        compute='_compute_document_ref',
        help='Link to the document. Empty when the document no longer exists.',
    )
    document_missing = fields.Boolean(
        string='Document Deleted', compute='_compute_document',
        help='Set when the document the activity points at no longer exists, '
             'or belongs to a model that is no longer installed.',
    )

    # ------------------------------------------------------------------
    # Document resolution
    # ------------------------------------------------------------------
    @api.model
    @tools.ormcache()
    def _selection_document_model(self):
        """Models a document_ref may point to.

        Read from the registry rather than from ir.model on purpose: ir.model is
        only readable by Access Rights managers, so querying it here would make
        the field raise for a plain employee - the ORM evaluates this selection
        in the current user's environment on every Reference assignment.

        Cached: the answer only changes when a module is installed, which
        reloads the registry and drops this cache with it.
        """
        return [
            (model_name, self.env[model_name]._description or model_name)
            for model_name in sorted(self.env.registry)
            if not self.env[model_name]._abstract and not self.env[model_name]._transient
        ]

    def _group_by_model(self):
        """{res_model: [report rows]} for the rows that point at a document."""
        per_model = defaultdict(list)
        for report in self:
            if report.res_model and report.res_id:
                per_model[report.res_model].append(report)
        return per_model

    @api.depends('res_model', 'res_id', 'res_name')
    def _compute_document(self):
        """Resolve display names in bulk: one batch per model, never per row."""
        for report in self:
            report.document_name = report.res_name or ''
            report.document_missing = False
            if not (report.res_model and report.res_id):
                # Some versions allow an activity with no document at all.
                report.document_name = _('No linked document')

        for res_model, reports in self._group_by_model().items():
            if res_model not in self.env:
                # The module that defined the model was uninstalled: the row is
                # not "deleted", it simply cannot be resolved any more.
                for report in reports:
                    report.document_missing = True
                    report.document_name = (
                        _('Unavailable document (%s is not installed)') % res_model)
                continue
            existing_ids, names = self._document_names(
                res_model, [report.res_id for report in reports])
            for report in reports:
                if report.res_id in existing_ids:
                    report.document_name = (
                        names.get(report.res_id)
                        or report.res_name
                        or '%s,%s' % (res_model, report.res_id)
                    )
                else:
                    report.document_missing = True
                    report.document_name = (
                        _('%s (deleted)') % report.res_name if report.res_name
                        else _('Deleted record (%s, id %s)') % (res_model, report.res_id)
                    )

    @api.depends('res_model', 'res_id')
    def _compute_document_ref(self):
        """Link only to documents the user is actually allowed to open.

        A row visible only because the activity is assigned to the current user
        may point at a document that user cannot read. Referencing it anyway
        would make the form view raise an AccessError as soon as the web client
        resolves the reference, so such a row simply gets no link.
        """
        for report in self:
            report.document_ref = False
        for res_model, reports in self._group_by_model().items():
            readable_ids = self._readable_record_ids(
                res_model, {report.res_id for report in reports})
            for report in reports:
                if report.res_id in readable_ids:
                    report.document_ref = '%s,%s' % (res_model, report.res_id)

    def _document_names(self, res_model, res_ids):
        """Return (ids that still exist, {id: display name}) for one model.

        A constant number of queries for the whole batch, never one per row.
        They are wrapped in a savepoint: a model whose table is gone, or a
        display name the current user is not allowed to compute, must degrade
        to a placeholder instead of aborting the transaction and breaking the
        whole list.
        """
        if not res_model or res_model not in self.env:
            return set(), {}
        Model = self.env[res_model]
        if Model._abstract or Model._transient:
            return set(), {}
        res_ids = sorted({res_id for res_id in res_ids if res_id})
        if not res_ids:
            return set(), {}

        try:
            with self.env.cr.savepoint():
                # exists() is a single id query and does not check access.
                existing_ids = set(
                    Model.with_context(active_test=False).browse(res_ids).exists().ids)
        except Exception:  # noqa: BLE001 - see docstring
            _logger.warning(
                'activity.overdue.report: cannot check existence of %s records',
                res_model, exc_info=True)
            return set(), {}

        names = {}
        # Names are read only for the documents this user may read: display_name
        # is fetched for the whole batch at once and would raise for every row if
        # a single unreadable record (one visible only because the activity is
        # assigned to the user) were left in the batch.
        readable_ids = self._readable_record_ids(res_model, existing_ids) if existing_ids else set()
        if readable_ids:
            try:
                with self.env.cr.savepoint():
                    records = Model.with_context(active_test=False).browse(sorted(readable_ids))
                    # display_name is prefetched for the whole batch at once.
                    names = {record.id: record.display_name for record in records}
            except Exception:  # noqa: BLE001 - see docstring
                _logger.warning(
                    'activity.overdue.report: cannot read display names of %s',
                    res_model, exc_info=True)
                names = {}
        return existing_ids, names

    def action_open_document(self):
        """Open the document the activity is attached to."""
        self.ensure_one()
        if not self.res_model or not self.res_id or self.res_model not in self.env:
            raise UserError(
                _('This activity is not attached to a document that can be opened.'))
        if self.res_id not in self._readable_record_ids(self.res_model, [self.res_id]):
            raise UserError(
                _('The document this activity refers to (%s, id %s) is not available: '
                  'it has been deleted, or you are not allowed to open it.')
                % (self.res_model, self.res_id))
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'views': [(False, 'form')],
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------
    def _flush_activities(self):
        """mail.activity rows pending in the ORM must reach the table first:
        this report reads mail_activity through a database view."""
        activity = self.env['mail.activity']
        flush = getattr(activity, 'flush_model', None) or getattr(activity, 'flush')
        flush()

    def _readable_record_ids(self, res_model, res_ids):
        """Ids of `res_model` the current user may read - one query per model.

        Access rights and record rules of the document are applied by search()
        itself; nothing here runs as superuser.

        Nothing is readable through this method for the report model itself: an
        activity may legitimately be created on any model, including this one,
        and following that would send the visibility check into itself. The
        context flag closes the same loop one level deeper.
        """
        if (not res_model or res_model == self._name
                or self.env.context.get('activity_overdue_report_scan')
                or res_model not in self.env):
            return set()
        Model = self.env[res_model]
        if Model._abstract or Model._transient:
            return set()
        try:
            with self.env.cr.savepoint():
                return set(Model.with_context(active_test=False,
                                              activity_overdue_report_scan=True)
                           .search([('id', 'in', list(res_ids))]).ids)
        except AccessError:
            # No read access on that model at all: none of its rows are visible.
            return set()
        except Exception:  # noqa: BLE001 - a broken model must hide rows, not crash
            _logger.warning(
                'activity.overdue.report: cannot check read access on %s',
                res_model, exc_info=True)
            return set()

    def _cap_candidate_rows(self, rows):
        """Bound the per-query cost of the visibility check, fail-closed."""
        if len(rows) > ACCESS_SCAN_LIMIT:
            _logger.warning(
                'activity.overdue.report: %s candidate rows exceed the %s row '
                'visibility-check ceiling; the answer is truncated.',
                len(rows), ACCESS_SCAN_LIMIT)
            return rows[:ACCESS_SCAN_LIMIT]
        return rows

    def _candidate_rows(self, candidate_ids):
        """(id, res_model, res_id, user_id) for the given report ids."""
        # self._table is derived from _name; the ids are bound parameters.
        self.env.cr.execute(
            'SELECT id, res_model, res_id, user_id FROM "%s" WHERE id IN %%s' % self._table,
            (tuple(candidate_ids),))
        return self.env.cr.fetchall()

    def _visible_ids_from_rows(self, rows):
        """Ids of `rows` the current user is allowed to see, in row order.

        A row is visible when the activity is assigned to the current user (the
        rule Odoo itself applies to mail.activity), or when the user can read
        the document the activity is attached to. Everything else - including
        rows whose document was deleted and rows on a model the user cannot
        read at all - is dropped.
        """
        uid = self.env.uid
        wanted = defaultdict(set)
        for __, res_model, res_id, user_id in rows:
            if user_id != uid and res_model and res_id:
                wanted[res_model].add(res_id)
        allowed = {
            res_model: self._readable_record_ids(res_model, res_ids)
            for res_model, res_ids in wanted.items()
        }
        return [
            row_id
            for row_id, res_model, res_id, user_id in rows
            if user_id == uid or (res_model and res_id in allowed.get(res_model, ()))
        ]

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, *args, **kwargs):
        """Drop the rows whose document the user may not read.

        Same approach as Odoo's own mail.activity._search. This single hook also
        covers grouping and counting, because read_group() and search_count()
        both build their query through _search() on this Odoo series.
        """
        self._flush_activities()
        query = super()._search(domain, offset, limit, order, *args, **kwargs)
        if self.env.su or kwargs.get('bypass_access'):
            return query
        # One pass: the candidate ids and the columns the check needs come out
        # of the same query, in the order the caller asked for.
        table = self._table
        self.env.cr.execute(query.select(
            '"%s"."id"' % table, '"%s"."res_model"' % table,
            '"%s"."res_id"' % table, '"%s"."user_id"' % table,
        ))
        rows = self._cap_candidate_rows(self.env.cr.fetchall())
        return self.browse(self._visible_ids_from_rows(rows))._as_query(order)

    def read(self, fields=None, load='_classic_read'):
        """Second line of defence: a direct read() must not bypass _search()."""
        if self._ids and not self.env.su:
            self._flush_activities()
            row_ids = list(self._ids)
            allowed = set()
            # Chunked, never truncated: in this path a dropped id would become a
            # wrong "access denied" instead of a merely shorter list.
            for start in range(0, len(row_ids), ACCESS_SCAN_LIMIT):
                chunk = row_ids[start:start + ACCESS_SCAN_LIMIT]
                allowed.update(self._visible_ids_from_rows(self._candidate_rows(chunk)))
            if any(row_id not in allowed for row_id in row_ids):
                raise AccessError(_(
                    'You are not allowed to read these overdue-activity rows, '
                    'because you cannot read the documents they are attached to.'))
        return super().read(fields=fields, load=load)

    # ------------------------------------------------------------------
    # Database view
    # ------------------------------------------------------------------
    def _report_view_sql(self):
        return REPORT_VIEW_SQL

    def init(self):
        # Read-only database view: this module never writes to mail.activity.
        # The only interpolated values are self._table (derived from _name) and
        # a module constant - no user input reaches this statement.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            'CREATE VIEW %s AS (%s)' % (self._table, self._report_view_sql()))
