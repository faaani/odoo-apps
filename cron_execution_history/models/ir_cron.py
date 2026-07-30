# -*- coding: utf-8 -*-
# Part of cron_execution_history. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
import threading
import time

from odoo import _, fields, models

from .cron_execution_history import log_execution

_logger = logging.getLogger(__name__)

# From 18.0 a job is not one call: ir.cron._run_job() calls _callback() again
# and again (up to MAX_BATCH_PER_CRON_JOB times) for server actions that use the
# progress API, and catches the exception of each batch itself. The run a user
# cares about is the whole job, so the row is written once in _run_job and
# _callback only remembers the failure of the last batch. Both run in the same
# cron worker thread, and the job cursor _run_job opens is not reachable from
# outside it, so the hand-over is a thread-local.
_JOB = threading.local()
# Value of the completion status core returns for a job that failed outright
# (CompletionStatus.FAILED). Compared as a plain string so this module does not
# import a private core symbol.
STATUS_FAILED = 'failed'


class IrCron(models.Model):
    _inherit = 'ir.cron'

    execution_history_count = fields.Integer(
        string='Recorded Runs', compute='_compute_execution_history_count',
        help='Number of runs of this scheduled action kept in the history.',
    )

    def _compute_execution_history_count(self):
        history = self.env['cron.execution.history']
        for cron in self:
            # One SQL count per record, and it still applies access rights.
            # This field is rendered on the scheduled action FORM only - do not
            # add it to a list view without batching this first.
            cron.execution_history_count = history.search_count(
                [('cron_ref', '=', cron.id)]) if cron.id else 0

    def action_open_execution_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Execution History'),
            'res_model': 'cron.execution.history',
            'view_mode': 'list,pivot,form',
            'domain': [('cron_ref', '=', self.id)],
            'context': {'create': False},
        }

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------
    def _log_cron_execution(self, cron_ref, cron_name, started_at, counter,
                            error=None):
        """Record one run. See log_execution() for why it commits on its own
        cursor and why it never raises."""
        return log_execution(self.env.registry, cron_ref, cron_name, started_at,
                             counter, error)

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    @classmethod
    def _run_job(cls, job):
        """Record one row per JOB - not per batch of a job.

        Core executes a job as a loop of _callback() calls and decides on a
        completion status; that status is Odoo's own verdict on the run, so it
        is what the history stores.
        """
        started_at = fields.Datetime.now()
        counter = time.monotonic()
        _JOB.error = None
        cron_ref, cron_name = job.get('id'), job.get('cron_name')
        try:
            status = super(IrCron, cls)._run_job(job)
        except Exception as error:
            # Core normally swallows the job exception per batch; if one still
            # gets out, record it and hand it straight back.
            log_execution(cls.pool, cron_ref, cron_name, started_at, counter,
                          error)
            raise
        error = getattr(_JOB, 'error', None) if status == STATUS_FAILED else None
        if status == STATUS_FAILED and error is None:
            # Failed without an exception reaching _callback (should not happen,
            # but the row must still say "failure" rather than silently pass).
            error = RuntimeError('The scheduled action failed.')
        log_execution(cls.pool, cron_ref, cron_name, started_at, counter, error)
        return status

    def _callback(self, cron_name, server_action_id):
        """Remember the failure of one batch for _run_job, and re-raise it.

        18.0 signature: (cron_name, server_action_id), called on the cron
        record. Odoo's own error handling stays in charge - nothing is
        swallowed or added here.
        """
        try:
            return super(IrCron, self)._callback(cron_name, server_action_id)
        except Exception as error:
            try:
                _JOB.error = error
            except Exception:  # noqa: BLE001 - never break the job
                _logger.exception('Scheduled Action History: cannot capture the '
                                  'failure of %r.', cron_name)
            raise

    def method_direct_trigger(self):
        """Record runs started with the "Run Manually" button too.

        On this series the button runs the server action directly instead of
        going through _run_job, so without this the run would not be recorded.
        """
        self.ensure_one()
        # Read the identity BEFORE running: a failing action leaves the
        # transaction aborted, and reading a field would then raise.
        cron_ref, cron_name = self.id, self.name
        started_at = fields.Datetime.now()
        counter = time.monotonic()
        try:
            result = super(IrCron, self).method_direct_trigger()
        except Exception as error:
            self._log_cron_execution(cron_ref, cron_name, started_at, counter,
                                     error)
            raise
        self._log_cron_execution(cron_ref, cron_name, started_at, counter)
        return result
