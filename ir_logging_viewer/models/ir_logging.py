# -*- coding: utf-8 -*-
# Part of ir_logging_viewer. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PARAM_RETENTION_ACTIVE = 'ir_logging_viewer.retention_active'
PARAM_RETENTION_DAYS = 'ir_logging_viewer.retention_days'

DEFAULT_RETENTION_DAYS = 30
MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 3650
# Length of the shortened message shown in the list view. The stored message is
# never modified: only this computed preview is cut.
PREVIEW_LENGTH = 150
# Batch size of the ORM deletion fallback (see _logging_viewer_delete).
ORM_DELETE_BATCH = 1000

# ir_logging.level is a free Char. The database log handler writes the uppercase
# python level name (INFO, WARNING, ERROR...) while an "Execute Python Code"
# server action calling log(message, level='info') writes it in lowercase. Both
# spellings are listed explicitly so the shipped filters stay index friendly -
# an ilike with a leading wildcard would scan the whole log table.
SEVERITY_LEVELS = [
    ('critical', ('CRITICAL', 'FATAL')),
    ('error', ('ERROR',)),
    ('warning', ('WARNING', 'WARN')),
    ('info', ('INFO',)),
    ('debug', ('DEBUG', 'NOTSET')),
]
SEVERITY_BY_LEVEL = {
    level: severity
    for severity, levels in SEVERITY_LEVELS
    for level in levels
}


class IrLogging(models.Model):
    _inherit = 'ir.logging'

    severity = fields.Selection(
        selection=[
            ('debug', 'Debug'),
            ('info', 'Info'),
            ('warning', 'Warning'),
            ('error', 'Error'),
            ('critical', 'Critical'),
            ('other', 'Other'),
        ],
        string='Severity', compute='_compute_severity',
        help='The raw Level value normalised to a fixed list, used to colour '
             'the list view. It is deliberately not stored: log rows are '
             'inserted by the server with plain SQL, so a stored column could '
             'never be kept up to date. Filter and group on Level instead.',
    )
    # Deliberately not labelled "Message": ir.logging already has a field with
    # that label, and two same-labelled fields on one model confuse exports.
    message_preview = fields.Char(
        string='Message Preview', compute='_compute_message_preview',
        help='First line of the message, shortened for the list view. Open the '
             'entry to read the complete message and traceback.',
    )

    @api.depends('level')
    def _compute_severity(self):
        for record in self:
            raw = (record.level or '').strip().upper()
            record.severity = SEVERITY_BY_LEVEL.get(raw, 'other')

    @api.depends('message')
    def _compute_message_preview(self):
        for record in self:
            message = (record.message or '').strip()
            first_line = message.split('\n', 1)[0].strip()
            preview = first_line[:PREVIEW_LENGTH]
            if len(preview) < len(message):
                preview = '%s ...' % preview.rstrip()
            record.message_preview = preview

    # ------------------------------------------------------------------
    # retention setting
    # ------------------------------------------------------------------
    @api.model
    def _logging_viewer_retention(self):
        """Return the retention setting as ``{'active': bool, 'days': int}``.

        Read with an explicit parser rather than a ``config_parameter=`` field:
        ``get_param`` hands back the default for any falsy stored value, so a
        Boolean stored as "False" could never be read back correctly.
        """
        params = self.env['ir.config_parameter'].sudo()
        raw_active = params.get_param(PARAM_RETENTION_ACTIVE, '')
        raw_days = params.get_param(PARAM_RETENTION_DAYS, '')
        try:
            days = int(raw_days)
        except (TypeError, ValueError):
            days = DEFAULT_RETENTION_DAYS
        return {
            # unset means off: this module never deletes anything until an
            # administrator turns the cleanup on.
            'active': str(raw_active).strip().lower() in ('1', 'true', 'yes'),
            'days': min(max(days, MIN_RETENTION_DAYS), MAX_RETENTION_DAYS),
        }

    @api.model
    def _logging_viewer_set_retention(self, active, days):
        """Store the retention setting after validating the window."""
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 0
        if not MIN_RETENTION_DAYS <= days <= MAX_RETENTION_DAYS:
            raise UserError(_(
                'Keep log entries for a number of days between %(min)s and %(max)s.'
            ) % {'min': MIN_RETENTION_DAYS, 'max': MAX_RETENTION_DAYS})
        params = self.env['ir.config_parameter'].sudo()
        params.set_param(PARAM_RETENTION_ACTIVE, 'True' if active else 'False')
        params.set_param(PARAM_RETENTION_DAYS, str(days))

    # ------------------------------------------------------------------
    # counting / deleting
    # ------------------------------------------------------------------
    @api.model
    def _logging_viewer_count(self, cutoff=None):
        """Number of log entries, or of entries created before ``cutoff``."""
        domain = [('create_date', '<', cutoff)] if cutoff else []
        return self.env['ir.logging'].search_count(domain)

    @api.model
    def _logging_viewer_gc(self):
        """Cron entry point: apply the configured retention window."""
        config = self._logging_viewer_retention()
        if not config['active']:
            _logger.debug(
                'Server Log Viewer: retention cleanup is off, no log entry removed.')
            return 0
        removed = self._logging_viewer_delete_older_than(config['days'])
        if removed:
            _logger.info(
                'Server Log Viewer: removed %s log entries older than %s days.',
                removed, config['days'])
        return removed

    @api.model
    def _logging_viewer_delete_older_than(self, days):
        """Delete entries older than ``days`` days, keep everything newer."""
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 0
        if days < MIN_RETENTION_DAYS:
            raise UserError(_('The retention window must be at least one day.'))
        cutoff = fields.Datetime.now() - timedelta(days=days)
        return self._logging_viewer_delete(cutoff=cutoff)

    @api.model
    def _logging_viewer_delete(self, cutoff=None):
        """Delete log entries - all of them when ``cutoff`` is not given.

        Nothing here runs under ``sudo()``: the caller's delete right on
        ir.logging is checked first. A log table can hold millions of rows, so
        the deletion is a single statement instead of a row by row browse -
        unless a record rule narrows what the caller may see, in which case the
        ORM does the work in batches and applies that rule.

        :return: the number of deleted entries.
        """
        self._logging_viewer_check_unlink()
        if self.env['ir.rule'].sudo().search_count([('model_id.model', '=', 'ir.logging')]):
            # sudo() is used only to *read* the rule definitions, in order to be
            # more restrictive - never to widen what the caller may delete.
            return self._logging_viewer_delete_via_orm(cutoff=cutoff)
        self._logging_viewer_flush()
        if cutoff:
            self.env.cr.execute(
                'DELETE FROM ir_logging WHERE create_date < %s', (cutoff,))
        else:
            self.env.cr.execute('DELETE FROM ir_logging')
        removed = self.env.cr.rowcount
        self._logging_viewer_invalidate()
        return removed

    @api.model
    def _logging_viewer_delete_via_orm(self, cutoff=None):
        """Record-rule aware deletion, in batches so memory stays bounded."""
        domain = [('create_date', '<', cutoff)] if cutoff else []
        logs = self.env['ir.logging']
        removed = 0
        while True:
            batch = logs.search(domain, limit=ORM_DELETE_BATCH)
            if not batch:
                break
            count = len(batch)
            batch.unlink()
            removed += count
        return removed

    @api.model
    def _logging_viewer_check_unlink(self):
        """Raise AccessError unless the caller may delete ir.logging rows."""
        logs = self.env['ir.logging']
        # 18.0 merged check_access_rights/check_access_rule into check_access.
        checker = getattr(logs, 'check_access', None)
        if checker is not None:
            checker('unlink')
        else:
            logs.check_access_rights('unlink')

    @api.model
    def _logging_viewer_flush(self):
        """Push pending ORM writes to the table before running raw SQL."""
        if hasattr(self.env, 'flush_all'):
            self.env.flush_all()
        else:
            self.env['ir.logging'].flush()

    @api.model
    def _logging_viewer_invalidate(self):
        """Drop cached values that the raw DELETE just made obsolete."""
        if hasattr(self.env, 'invalidate_all'):
            self.env.invalidate_all()
        else:
            self.env['ir.logging'].invalidate_cache()
