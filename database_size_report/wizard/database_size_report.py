# -*- coding: utf-8 -*-
# Part of database_size_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

MB = 1024.0 * 1024.0
# How many of the biggest tables the report lists by default. The header totals
# always cover every table, and the form says so when the list is truncated.
DEFAULT_LINE_LIMIT = 100
MAX_LINE_LIMIT = 2000

# The listing statement: static and parameterless (the database size is read by a
# second, equally static one below). Nothing here is built from user input, so
# there is no place for SQL injection: the only thing the user can change is how
# many of the returned rows end up on screen.
#
# pg_table_size()          = heap + TOAST + free space map + visibility map
# pg_indexes_size()        = every index of the table
# pg_total_relation_size() = the sum of both, which is what "this table costs" means
# reltuples               = PostgreSQL's own row estimate, maintained by
#                           ANALYZE/autovacuum. It is free to read, while
#                           COUNT(*) would scan every table in the database.
#                           PostgreSQL 14+ stores -1 for a table that has never
#                           been analysed, which is reported as "no statistics".
SIZE_QUERY = """
    SELECT n.nspname                         AS schema_name,
           c.relname                         AS table_name,
           c.relkind                         AS relkind,
           GREATEST(c.reltuples, 0)::bigint  AS row_estimate,
           (c.reltuples < 0)                 AS row_estimate_missing,
           pg_table_size(c.oid)              AS table_bytes,
           pg_indexes_size(c.oid)            AS index_bytes,
           pg_total_relation_size(c.oid)     AS total_bytes
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relkind IN ('r', 'p', 'm')
       AND n.nspname NOT IN ('pg_catalog', 'information_schema')
       AND left(n.nspname, 3) <> 'pg_'
  ORDER BY pg_total_relation_size(c.oid) DESC, n.nspname, c.relname
"""

# Also static and parameterless.
DATABASE_SIZE_QUERY = ("SELECT current_database(), pg_database_size(current_database()), "
                       "current_schema()")

RELKIND_LABELS = {
    'r': 'table',
    'p': 'partitioned',
    'm': 'matview',
}


def format_size(num_bytes):
    """Return a human readable size, e.g. 1.44 MB."""
    num = float(num_bytes or 0)
    if num < 1024.0:
        return '%d B' % int(num)
    for unit in ('KB', 'MB', 'GB'):
        num /= 1024.0
        if abs(num) < 1024.0:
            return '%.2f %s' % (num, unit)
    return '%.2f TB' % (num / 1024.0)


class DatabaseSizeReport(models.TransientModel):
    _name = 'database.size.report'
    _description = 'Database Size Report'

    # keeps the breadcrumb readable instead of "database.size.report,4"
    name = fields.Char(
        string='Report', readonly=True,
        default=lambda self: _('Database Size Report'))
    line_limit = fields.Integer(
        string='Tables to List', default=DEFAULT_LINE_LIMIT,
        help='How many of the largest tables to list (1-%s). The totals above '
             'always cover every table, whatever this is set to.' % MAX_LINE_LIMIT)

    database_name = fields.Char(string='Database', readonly=True)
    measured_on = fields.Datetime(string='Measured On', readonly=True)
    database_size_bytes = fields.Float(
        string='Database Size (bytes)', readonly=True, digits=(16, 0))
    database_size_display = fields.Char(
        string='Database on Disk', readonly=True,
        help='What PostgreSQL reports for the whole database (pg_database_size): '
             'user tables, system catalogs and the free space left behind by '
             'deleted rows. It is therefore larger than the total of the tables.')
    total_bytes = fields.Float(
        string='Tables Total (bytes)', readonly=True, digits=(16, 0))
    total_display = fields.Char(
        string='All Tables + Indexes', readonly=True,
        help='Total size of every table in the database, including its indexes '
             'and TOAST storage.')
    listed_bytes = fields.Float(
        string='Listed Total (bytes)', readonly=True, digits=(16, 0))
    listed_display = fields.Char(
        string='Listed Tables + Indexes', readonly=True,
        help='Total size of the tables shown in the list below.')
    table_count = fields.Integer(string='Tables in Database', readonly=True)
    listed_count = fields.Integer(string='Tables Listed', readonly=True)
    is_truncated = fields.Boolean(
        string='List Truncated', readonly=True,
        help='Ticked when the database holds more tables than the list shows.')

    line_ids = fields.One2many(
        'database.size.report.line', 'report_id', string='Tables', readonly=True)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _check_report_access(self):
        """The report measures every table in the database, including tables the
        user has no access to, so it is reserved to Settings administrators."""
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_(
                'Only Settings administrators may run the Database Size Report.'))

    @api.model
    def _model_by_table(self):
        """Map physical table name -> (model name, translated model label).

        Built from the registry rather than from ``model.replace('.', '_')``
        because models are free to set their own ``_table``: ``ir.actions.act_window``
        lives in ``ir_act_window``, and guessing would mislabel it.
        """
        mapping = {}
        registry = self.env.registry
        for data in self.env['ir.model'].search_read([], ['model', 'name']):
            model_name = data['model']
            if model_name not in registry:
                continue
            model = self.env[model_name]
            if model._abstract:
                continue  # abstract models have no storage of their own
            table = getattr(model, '_table', None)
            if not table:
                continue
            # several models can share one table; keep a stable, predictable pick
            current = mapping.get(table)
            if current is None or model_name < current[0]:
                mapping[table] = (model_name, data['name'] or model_name)
        return mapping

    @api.model
    def _table_notes(self):
        """Plain-language notes for the tables that are usually responsible when
        a database balloons. Descriptive only: the report never suggests, and
        never performs, any deletion."""
        return {
            'mail_message': _(
                'Chatter messages: one row per logged note, e-mail and '
                'tracked-change message, on every record of every model.'),
            'mail_tracking_value': _(
                'The old/new values behind the "tracked changes" lines in the '
                'chatter. Grows with mail_message.'),
            'mail_notification': _(
                'One row per recipient of every chatter message, so it grows '
                'faster than mail_message itself.'),
            'mail_followers': _('One row per follower of every record.'),
            'ir_attachment': _(
                'Attachment metadata. The files themselves live in the '
                'filestore on disk unless they are stored in the database.'),
            'ir_logging': _('Server log lines written into the database by modules.'),
            'ir_cron_trigger': _('Queued one-off triggers for scheduled actions.'),
            'bus_bus': _('Real-time notification bus. Odoo empties it on its own.'),
            'res_users_log': _(
                'One row per login. Odoo keeps only the latest row per user.'),
        }

    @api.model
    def _note_for_table(self, table_name):
        note = self._table_notes().get(table_name)
        if note:
            return note
        if table_name.endswith('_log') or table_name.endswith('_history'):
            return _('History/log table: rows accumulate over time.')
        return False

    def _effective_limit(self):
        self.ensure_one()
        return min(max(self.line_limit or DEFAULT_LINE_LIMIT, 1), MAX_LINE_LIMIT)

    # ------------------------------------------------------------------
    # report
    # ------------------------------------------------------------------
    def _measure(self):
        """Read the sizes straight from the PostgreSQL catalog.

        Returns a dict with the database name, its size on disk, the schema Odoo
        itself writes to, and the table ``rows`` already sorted biggest first.
        Both statements are constant strings.
        """
        cr = self.env.cr
        cr.execute(DATABASE_SIZE_QUERY)
        database_name, database_bytes, odoo_schema = cr.fetchone()
        cr.execute(SIZE_QUERY)
        return {
            'database_name': database_name,
            'database_bytes': float(database_bytes or 0),
            'odoo_schema': odoo_schema or 'public',
            'rows': cr.dictfetchall(),
        }

    def _compute_report(self):
        """Refresh the header totals and the list of the biggest tables."""
        self.ensure_one()
        self._check_report_access()
        measure = self._measure()
        database_name = measure['database_name']
        database_bytes = measure['database_bytes']
        odoo_schema = measure['odoo_schema']
        rows = measure['rows']

        total = sum(float(row['total_bytes'] or 0) for row in rows)
        limit = self._effective_limit()
        listed = rows[:limit]
        listed_total = sum(float(row['total_bytes'] or 0) for row in listed)

        models_by_table = self._model_by_table()
        line_vals = []
        for row in listed:
            table_name = row['table_name']
            # A table of the same name in another schema is NOT the Odoo table:
            # a staging or analytics schema holding its own copy of res_partner
            # must not be reported as storing res.partner, and must not inherit
            # the note either.
            is_odoo_schema = row['schema_name'] == odoo_schema
            model_name, model_label = (
                models_by_table.get(table_name, (False, False))
                if is_odoo_schema else (False, False))
            note = self._note_for_table(table_name) if is_odoo_schema else False
            row_total = float(row['total_bytes'] or 0)
            line_vals.append((0, 0, {
                'schema_name': row['schema_name'],
                'table_name': table_name,
                'kind': RELKIND_LABELS.get(row['relkind'], 'table'),
                'model_name': model_name,
                'model_label': model_label,
                'row_estimate': float(row['row_estimate'] or 0),
                'row_estimate_missing': bool(row['row_estimate_missing']),
                'table_bytes': float(row['table_bytes'] or 0),
                'index_bytes': float(row['index_bytes'] or 0),
                'total_bytes': row_total,
                'total_mb': row_total / MB,
                'table_size': format_size(row['table_bytes']),
                'index_size': format_size(row['index_bytes']),
                'total_size': format_size(row_total),
                'percentage': (row_total / total * 100.0) if total else 0.0,
                'note': note,
            }))

        self.write({
            'database_name': database_name,
            'measured_on': fields.Datetime.now(),
            'database_size_bytes': database_bytes,
            'database_size_display': format_size(database_bytes),
            'total_bytes': total,
            'total_display': format_size(total),
            'listed_bytes': listed_total,
            'listed_display': format_size(listed_total),
            'table_count': len(rows),
            'listed_count': len(listed),
            'is_truncated': len(listed) < len(rows),
            'line_ids': [(5, 0, 0)] + line_vals,
        })

    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Database Size Report'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    @api.model
    def action_open_report(self):
        """Entry point of the menu: measure the database and show the result."""
        self._check_report_access()
        report = self.create({})
        report._compute_report()
        return report._reopen()

    def action_refresh(self):
        """Measure again, e.g. after changing how many tables to list."""
        self.ensure_one()
        self._compute_report()
        return self._reopen()

    def action_open_lines(self):
        """Open the same lines as a full list view, for filtering and export."""
        self.ensure_one()
        self._check_report_access()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'database_size_report.action_database_size_report_line')
        action['domain'] = [('report_id', '=', self.id)]
        action['context'] = {}
        return action


class DatabaseSizeReportLine(models.TransientModel):
    _name = 'database.size.report.line'
    _description = 'Database Table Size'
    _rec_name = 'table_name'
    _order = 'total_bytes desc, table_name'

    report_id = fields.Many2one(
        'database.size.report', string='Report', required=True,
        ondelete='cascade', index=True)
    table_name = fields.Char(string='Table', readonly=True)
    schema_name = fields.Char(string='Schema', readonly=True)
    kind = fields.Selection(
        [('table', 'Table'), ('partitioned', 'Partitioned Table'),
         ('matview', 'Materialized View')],
        string='Kind', readonly=True)
    model_name = fields.Char(
        string='Odoo Model', readonly=True,
        help='The model stored in this table. Empty for tables that belong to '
             'no model, such as the relation tables behind many2many fields.')
    model_label = fields.Char(string='Model Name', readonly=True)
    row_estimate = fields.Float(
        string='Rows (estimate)', readonly=True, digits=(16, 0),
        help='PostgreSQL\'s own row estimate (reltuples), refreshed by ANALYZE '
             'and autovacuum. It is not an exact count: reading it is instant '
             'even on a huge table, while COUNT(*) would read the whole table.')
    row_estimate_missing = fields.Boolean(
        string='No Statistics', readonly=True,
        help='Ticked when PostgreSQL has never analysed this table, so no row '
             'estimate exists yet and 0 is shown. PostgreSQL 14 and above only: '
             'older versions cannot tell an unanalysed table from an empty one.')
    table_bytes = fields.Float(string='Table (bytes)', readonly=True, digits=(16, 0))
    index_bytes = fields.Float(string='Indexes (bytes)', readonly=True, digits=(16, 0))
    total_bytes = fields.Float(string='Total (bytes)', readonly=True, digits=(16, 0))
    total_mb = fields.Float(string='Total (MB)', readonly=True, digits=(16, 2))
    table_size = fields.Char(string='Table Size', readonly=True)
    index_size = fields.Char(string='Index Size', readonly=True)
    total_size = fields.Char(string='Total Size', readonly=True)
    percentage = fields.Float(
        string='Share', readonly=True, digits=(16, 2),
        help='Share of the total size of all tables in the database.')
    note = fields.Char(
        string='Note', readonly=True,
        help='What this table usually holds, for the tables that most often '
             'explain a growing database.')
