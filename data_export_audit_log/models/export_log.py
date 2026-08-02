# -*- coding: utf-8 -*-
# Part of data_export_audit_log. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

PARAM_RETENTION_DAYS = 'data_export_audit_log.retention_days'
DEFAULT_RETENTION_DAYS = 180
PURGE_BATCH_SIZE = 10000


class ExportLog(models.Model):
    """Audit trail of data exports.

    Audit-telemetry invariant: rows are created ONLY by the export hook
    (models/base.py) under sudo(). The ACL deliberately grants create/write
    to nobody - not even Settings users - so the trail cannot be forged or
    edited from the UI or through the ORM. sudo() bypasses the ACL, which is
    exactly the single path allowed to write here. Settings users get read
    and unlink only.
    """
    _name = 'export.audit.log'
    _description = 'Export Audit Log'
    _rec_name = 'model_description'
    # id is monotonic with create_date on an insert-only table, so ordering
    # by id rides the primary key index instead of an unindexed date sort
    _order = 'id desc'

    user_id = fields.Many2one(
        'res.users', string='User', index=True,
        ondelete='set null', readonly=True,
        help='User who performed the export.')
    user_login = fields.Char(
        string='Login', required=True, index=True, readonly=True,
        help='Login of the exporting user, kept even if the user record '
             'is later deleted.')
    model_name = fields.Char(
        string='Model (technical)', required=True, index=True, readonly=True,
        help='Technical name of the exported model, e.g. res.partner.')
    model_description = fields.Char(
        string='Model', readonly=True,
        help='Human-readable label of the exported model.')
    record_count = fields.Integer(
        string='Records', readonly=True,
        help='Total number of records included in the export.')
    field_list = fields.Text(
        string='Exported Fields', readonly=True,
        help='Comma-separated list of the exported field paths '
             '(truncated when very long).')

    @api.model
    def _audit_flush_pending(self, cr):
        """Precommit hook: write one log row per (user, model) accumulated
        on this cursor by the export hook (see models/base.py).

        Each row gets its own savepoint with flush=False plus an explicit
        flush of the new record only: any failure - constraint, DB error,
        anything - rolls back that log row alone, never the caller's
        transaction, and a flushing savepoint here would re-run precommit
        hooks on 14.0/15.0.
        """
        pending = cr.__dict__.pop('_export_audit_pending', None)
        if not pending:
            return
        for (uid, model_name), entry in pending.items():
            try:
                with cr.savepoint(flush=False):
                    ir_model = self.env['ir.model'].sudo()._get(model_name)
                    user = self.env['res.users'].sudo().browse(uid)
                    # sudo: the hook must write although the ACL grants
                    # create to nobody (audit-telemetry invariant above)
                    log = self.sudo().create({
                        'user_id': uid,
                        'user_login': user.login or 'uid %d' % uid,
                        'model_name': model_name,
                        'model_description':
                            ir_model.name if ir_model else model_name,
                        'record_count': entry['count'],
                        'field_list': entry['fields'] or '',
                    })
                    if hasattr(log, 'flush_recordset'):
                        log.flush_recordset()
                    else:  # 14.0 / 15.0
                        log.flush()
            except Exception:
                _logger.warning(
                    "data_export_audit_log: could not write the export log "
                    "row for %s (uid %s); the export itself is unaffected",
                    model_name, uid, exc_info=True)

    @api.model
    def _get_retention_days(self):
        """Retention in days; 0 means keep forever. Robust against bad
        input: a negative or non-numeric parameter value falls back to the
        default instead of silently meaning "keep forever"."""
        icp = self.env['ir.config_parameter'].sudo()
        raw = icp.get_param(PARAM_RETENTION_DAYS, str(DEFAULT_RETENTION_DAYS))
        try:
            days = int(raw)
        except (TypeError, ValueError):
            return DEFAULT_RETENTION_DAYS
        if days < 0:
            return DEFAULT_RETENTION_DAYS
        return days

    @api.model
    def _purge_old_logs(self):
        """Scheduled action: delete log rows older than the retention period.

        Raw SQL in batches: the table can grow large, export.audit.log rows
        have no ORM side effects to preserve, and batching keeps each DELETE
        statement's work and memory bounded (all batches still run inside
        the cron's single transaction). The cutoff is resolved to an id once
        (id is monotonic with create_date on this insert-only table), then
        deleted PURGE_BATCH_SIZE rows at a time.
        """
        days = self._get_retention_days()
        if not days:
            return 0
        cutoff = fields.Datetime.now() - timedelta(days=days)
        self.env.cr.execute(
            "SELECT max(id) FROM export_audit_log WHERE create_date < %s", (cutoff,))
        row = self.env.cr.fetchone()
        max_id = row and row[0]
        if not max_id:
            return 0
        deleted = 0
        while True:
            self.env.cr.execute(
                "DELETE FROM export_audit_log WHERE id IN "
                "(SELECT id FROM export_audit_log WHERE id <= %s LIMIT %s)",
                (max_id, PURGE_BATCH_SIZE))
            if not self.env.cr.rowcount:
                break
            deleted += self.env.cr.rowcount
        if deleted:
            # drop stale ORM cache entries for the rows removed by raw SQL
            if hasattr(self, 'invalidate_model'):
                self.invalidate_model()
            else:  # 14.0 / 15.0
                self.invalidate_cache()
            _logger.info(
                "data_export_audit_log: purged %d export log entries older "
                "than %d days", deleted, days)
        return deleted
