# -*- coding: utf-8 -*-
# Part of cron_execution_history. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
import time

from odoo import _, api, fields, models

from .cron_execution_history import log_execution

_logger = logging.getLogger(__name__)

# Odoo 14.0-17.0 do NOT let a job exception out of ir.cron._callback: the except
# clause routes it to _handle_callback_exception and returns normally. The
# exception is therefore handed over on the cursor object, the one thing both
# methods provably share, and read back right after the super() call.
ERROR_ATTR = '_cron_execution_history_error'


class IrCron(models.Model):
    _inherit = 'ir.cron'

    execution_history_count = fields.Integer(
        string='Recorded Runs', compute='_compute_execution_history_count',
        help='Number of runs of this scheduled action kept in the history.',
    )

    def _compute_execution_history_count(self):
        history = self.env['cron.execution.history']
        for cron in self:
            # search_count is a single SQL count that still applies access
            # rights; this field is only ever rendered on the cron form.
            cron.execution_history_count = history.search_count(
                [('cron_ref', '=', cron.id)]) if cron.id else 0

    def action_open_execution_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Execution History'),
            'res_model': 'cron.execution.history',
            'view_mode': 'tree,pivot,form',
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
    def _callback(self, cron_name, server_action_id, job_id):
        """Record one scheduled run. 14.0-17.0 signature: (name, action id, job id).

        On this series ``self`` is a model-level recordset (the scheduler calls
        the method on the model, not on a record), so the cron id comes from the
        ``job_id`` argument.
        """
        started_at = fields.Datetime.now()
        counter = time.monotonic()
        cr = self.env.cr
        try:
            setattr(cr, ERROR_ATTR, None)
        except Exception:  # noqa: BLE001 - never break the job
            _logger.exception('Scheduled Action History: cannot arm the failure '
                              'hand-over for %r.', cron_name)
        try:
            result = super(IrCron, self)._callback(
                cron_name, server_action_id, job_id)
        except Exception as error:
            # Odoo's own error handling stays in charge: record, then re-raise.
            self._log_cron_execution(job_id, cron_name, started_at, counter, error)
            raise
        self._log_cron_execution(job_id, cron_name, started_at, counter,
                                 getattr(cr, ERROR_ATTR, None))
        return result

    @api.model
    def _handle_callback_exception(self, cron_name, server_action_id, job_id,
                                   job_exception):
        """Capture the job exception core is about to swallow (14.0-17.0)."""
        try:
            setattr(self.env.cr, ERROR_ATTR, job_exception)
        except Exception:  # noqa: BLE001 - never break the job
            _logger.exception('Scheduled Action History: could not capture the '
                              'exception of %r.', cron_name)
        return super(IrCron, self)._handle_callback_exception(
            cron_name, server_action_id, job_id, job_exception)

    def method_direct_trigger(self):
        """Record runs started with the "Run Manually" button too.

        On this series the button runs the server action directly instead of
        going through _callback, so without this the run would not be recorded.
        """
        for cron in self:
            # Read the identity BEFORE running: a failing action leaves the
            # transaction aborted, and reading a field would then raise.
            cron_ref, cron_name = cron.id, cron.name
            started_at = fields.Datetime.now()
            counter = time.monotonic()
            try:
                super(IrCron, cron).method_direct_trigger()
            except Exception as error:
                self._log_cron_execution(cron_ref, cron_name, started_at,
                                         counter, error)
                raise
            self._log_cron_execution(cron_ref, cron_name, started_at, counter)
        return True
