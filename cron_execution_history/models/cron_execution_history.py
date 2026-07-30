# -*- coding: utf-8 -*-
# Part of cron_execution_history. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
import time
import traceback
from datetime import timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.tools import str2bool

_logger = logging.getLogger(__name__)

PARAM_ENABLED = 'cron_execution_history.enabled'
PARAM_LOG_SUCCESS = 'cron_execution_history.log_success'
PARAM_RETENTION_DAYS = 'cron_execution_history.retention_days'
CONFIG_PARAMS = (PARAM_ENABLED, PARAM_LOG_SUCCESS, PARAM_RETENTION_DAYS)

DEFAULT_RETENTION_DAYS = 30
# Upper bound on rows removed by one cleanup run: a first cleanup on a database
# that ran for months without retention must not hold a transaction open for
# minutes. What is left over is removed by the next daily run.
GC_BATCH_LIMIT = 20000
# ... and an upper bound on the number of batches, so one nightly run can catch
# up on a large backlog without turning into an hours-long job.
GC_MAX_BATCHES = 25
# Written when the scheduler hands over a job with no name at all. Deliberately
# untranslated: it is written from a cursor that may be running right after a
# failed transaction, where a translation lookup is one more thing that could go
# wrong for no benefit.
UNNAMED_ACTION = 'Unnamed scheduled action'
# Stored error text is bounded so a chatty traceback cannot bloat the table.
MESSAGE_LIMIT = 2000
TRACEBACK_LIMIT = 15000
TRUNCATED_SUFFIX = '\n[... truncated by Scheduled Action History]'


def parse_config(values):
    """Turn raw ``ir.config_parameter`` values into usable settings.

    Anything unreadable falls back to the default: these parameters can be
    hand-edited, and the recorder must never trip over a typo.

    :param values: mapping ``{parameter key: stored string}``.
    """
    def as_bool(key, default=True):
        raw = values.get(key)
        if not raw:
            return default
        try:
            return str2bool(raw)
        except ValueError:
            return default

    try:
        retention_days = int(values.get(PARAM_RETENTION_DAYS)
                             or DEFAULT_RETENTION_DAYS)
    except (TypeError, ValueError):
        retention_days = DEFAULT_RETENTION_DAYS
    return {
        'enabled': as_bool(PARAM_ENABLED),
        'log_success': as_bool(PARAM_LOG_SUCCESS),
        'retention_days': max(retention_days, 0),
    }


def shorten(text, limit):
    """Bound a stored error text, marking it when something was cut off."""
    if not text:
        return False
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + TRUNCATED_SUFFIX


def log_execution(registry, cron_ref, cron_name, started_at, counter, error=None):
    """Write one history row on a dedicated cursor and commit it.

    A failing job leaves its own transaction rolled back, so the history row
    cannot be written on the job cursor - it would disappear together with
    exactly the failure it is supposed to document. A separate cursor is opened
    and committed for the log row alone, and it only ever touches this module's
    own table and reads the module's settings.

    Plain SQL, no ORM, on purpose. On 14.0 the ORM's pending-write buffer is
    shared by every environment of the THREAD, not of the transaction: an ORM
    write here would flush the job's own pending UPDATEs onto this cursor, which
    self-deadlocks against the row lock the scheduler holds. SQL keeps the two
    transactions completely independent.

    A plain function rather than a method because 18.0/19.0 record from
    ``ir.cron._run_job``, a classmethod that has no environment - only the
    registry. Everything is defensive: recording a run must never change its
    outcome.
    """
    try:
        duration = max(time.monotonic() - counter, 0.0)
        error_type = error_message = error_traceback = None
        if error is not None:
            error_type = type(error).__name__
            # Formatting someone else's exception can itself fail (a __str__
            # that raises, an unprintable argument). Each text is best-effort on
            # its own so a bad message never costs the whole record.
            try:
                error_message = shorten(str(error) or error_type, MESSAGE_LIMIT)
            except Exception:  # noqa: BLE001
                error_message = error_type
            try:
                error_traceback = shorten(''.join(traceback.format_exception(
                    type(error), error, error.__traceback__)), TRACEBACK_LIMIT)
            except Exception:  # noqa: BLE001
                error_traceback = None
        with registry.cursor() as cr:
            # The settings are read on this cursor too: after a failure the job
            # cursor is rolled back and must not be queried again.
            cr.execute("SELECT key, value FROM ir_config_parameter "
                       "WHERE key IN %s", (CONFIG_PARAMS,))
            config = parse_config(dict(cr.fetchall()))
            if not config['enabled']:
                return False
            if error is None and not config['log_success']:
                return False
            cr.execute("""
                INSERT INTO cron_execution_history
                    (cron_ref, cron_name, state, start_time, end_time,
                     duration, error_type, error_message, error_traceback,
                     create_uid, create_date, write_uid, write_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, (now() AT TIME ZONE 'UTC'),
                        %s, (now() AT TIME ZONE 'UTC'))
            """, (
                cron_ref or 0,
                (cron_name or UNNAMED_ACTION)[:255],
                'failure' if error is not None else 'success',
                started_at,
                started_at + timedelta(seconds=duration),
                duration,
                error_type, error_message, error_traceback,
                SUPERUSER_ID, SUPERUSER_ID,
            ))
            # pylint: disable=invalid-commit
            # Not the job's transaction: this is a private cursor holding
            # nothing but the history row. Committing it here is what makes a
            # failure record survive the rollback of the failing job.
            cr.commit()
        return True
    except Exception:  # noqa: BLE001 - logging must never break a job
        _logger.exception('Scheduled Action History: could not record the run '
                          'of %r.', cron_name)
        return False


class CronExecutionHistory(models.Model):
    _name = 'cron.execution.history'
    _description = 'Scheduled Action Execution History'
    _order = 'start_time desc, id desc'
    _rec_name = 'cron_name'

    # The scheduled action is referenced by plain id + name instead of a
    # Many2one on purpose. The row is written from a SEPARATE transaction while
    # Odoo still holds a row lock on ir_cron for the running job; a foreign key
    # would make PostgreSQL ask for a FOR KEY SHARE lock on that very row, which
    # on 14.0 (FOR UPDATE) blocks until the job ends - i.e. forever. Keeping the
    # reference key-free also means history survives the deletion of an action.
    cron_ref = fields.Integer(
        string='Scheduled Action ID', index=True, readonly=True,
        help='Database id of the scheduled action this run belongs to.',
    )
    cron_name = fields.Char(
        string='Scheduled Action', required=True, index=True, readonly=True,
        help='Name of the scheduled action as it was when the run started.',
    )
    cron_id = fields.Many2one(
        'ir.cron', string='Open Action', compute='_compute_cron_id',
        help='Link back to the scheduled action. Empty when the action has been '
             'deleted since the run.',
    )
    state = fields.Selection(
        [('success', 'Success'), ('failure', 'Failure')],
        string='Result', required=True, index=True, readonly=True,
    )
    start_time = fields.Datetime(
        string='Started', required=True, index=True, readonly=True,
    )
    end_time = fields.Datetime(string='Finished', readonly=True)
    duration = fields.Float(
        string='Duration (s)', digits=(16, 3), readonly=True,
        aggregator='avg',
        help='Wall-clock seconds the run took. Aggregated as an average, so the '
             'pivot view shows the average duration per scheduled action.',
    )
    error_type = fields.Char(
        string='Error Type', readonly=True,
        help='Python class of the exception that ended the run.',
    )
    error_message = fields.Text(
        string='Error Message', readonly=True,
        help='Message of the exception that ended the run (truncated when very long).',
    )
    error_traceback = fields.Text(
        string='Traceback', readonly=True,
        help='Python traceback of the failure (truncated when very long).',
    )

    @api.depends('cron_ref')
    def _compute_cron_id(self):
        # One query for the whole recordset, and only ids that still exist:
        # browsing a deleted action would raise MissingError on display.
        refs = [record.cron_ref for record in self if record.cron_ref]
        alive = set(self.env['ir.cron'].browse(refs).exists().ids) if refs else set()
        for record in self:
            record.cron_id = record.cron_ref if record.cron_ref in alive else False

    @api.model
    def _history_config(self):
        """Read the module settings through the ORM.

        The recorder does NOT use this: it reads the same parameters with plain
        SQL on its own cursor (see ir_cron.py).
        """
        icp = self.env['ir.config_parameter'].sudo()
        return parse_config({key: icp.get_param(key) for key in CONFIG_PARAMS})

    @api.model
    def _gc_execution_history(self):
        """Delete history rows older than the retention setting.

        Only rows of this model are ever touched. Returns the number of deleted
        rows; 0 days of retention means "keep everything".
        """
        retention_days = self._history_config()['retention_days']
        if retention_days <= 0:
            _logger.info('Scheduled Action History: retention disabled, '
                         'nothing is deleted.')
            return 0
        cutoff = fields.Datetime.now() - timedelta(days=retention_days)
        total = 0
        for _batch in range(GC_MAX_BATCHES):
            # OLDEST first: the batch cap has to trim the tail of the backlog,
            # never its head. With the model's default order (newest first) the
            # oldest rows would be the ones the cap leaves behind, run after
            # run, and a large backlog would never drain.
            stale = self.search([('start_time', '<', cutoff)],
                                limit=GC_BATCH_LIMIT,
                                order='start_time asc, id asc')
            if not stale:
                break
            count = len(stale)
            stale.unlink()
            # pylint: disable=invalid-commit
            # This cron owns its transaction and only deletes its own rows.
            # Committing each batch keeps each transaction short, so a first
            # cleanup on a database that ran for months does not hold one
            # transaction open over millions of rows.
            self.env.cr.commit()
            total += count
            if count < GC_BATCH_LIMIT:
                break
        else:
            _logger.info('Scheduled Action History: removed %s rows and stopped '
                         'at the per-run limit; the rest goes on the next run.',
                         total)
        if total:
            _logger.info('Scheduled Action History: removed %s rows older than '
                         '%s days.', total, retention_days)
        return total

    def action_open_cron(self):
        """Open the scheduled action this run belongs to."""
        self.ensure_one()
        if not self.cron_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Scheduled Action'),
            'res_model': 'ir.cron',
            'res_id': self.cron_id.id,
            'view_mode': 'form',
        }
