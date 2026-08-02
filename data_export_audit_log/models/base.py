# -*- coding: utf-8 -*-
# Part of data_export_audit_log. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import models

_logger = logging.getLogger(__name__)

# storage cap for the exported-fields string (SPEC: ~2000 chars)
FIELD_LIST_MAX_CHARS = 2000


class Base(models.AbstractModel):
    _inherit = 'base'

    def export_data(self, fields_to_export):
        """Record the export, then run the standard export.

        Signature verified identical (self, fields_to_export) on every
        supported series. The web export controller does NOT call this once
        per user export: grouped list exports call it once per leaf group,
        and large flat exports call it once per 1000-record batch on newer
        series. The hook therefore only ACCUMULATES per (user, model) on the
        cursor and defers the actual log row to a precommit callback, so one
        user export ends up as one row with the real total record count.
        """
        self._audit_log_export(fields_to_export)
        return super(Base, self).export_data(fields_to_export)

    def _audit_log_export(self, fields_to_export):
        """Accumulate this export chunk for audit logging. Never raises.

        Skips: empty recordsets, transient models (wizard exports are
        transient plumbing, not data leaving the system), and export.audit.log
        itself (reading the audit log is not an auditable export).
        Superuser exports ARE logged - that is the point of an audit trail.
        """
        if not self or self._transient or self._name == 'export.audit.log':
            return
        if 'export.audit.log' not in self.env:
            # module being uninstalled / registry rebuilding
            return
        if getattr(self.env.cr, 'readonly', False):
            # 18.0/19.0 readonly cursor: nothing can be written here; the
            # export download routes are read-write, so this is a corner
            # case (e.g. custom readonly route calling export_data).
            _logger.warning(
                "data_export_audit_log: export of %s (%d records) by uid %s "
                "not logged (readonly cursor)",
                self._name, len(self), self.env.uid)
            return
        try:
            cr = self.env.cr
            pending = getattr(cr, '_export_audit_pending', None)
            if pending is None:
                pending = {}
                cr._export_audit_pending = pending
                # Registered OUTSIDE any savepoint: on 14.0/15.0 a flushing
                # savepoint runs precommit hooks on entry, which would fire
                # the callback mid-accumulation. If that ever happens the
                # rows written so far are still correct and the next chunk
                # simply re-registers.
                env = self.env
                cr.precommit.add(
                    lambda: env['export.audit.log']._audit_flush_pending(cr))
            key = (self.env.uid, self._name)
            entry = pending.get(key)
            if entry is None:
                entry = pending[key] = {'count': 0, 'fields': None}
            entry['count'] += len(self)
            if entry['fields'] is None:
                entry['fields'] = self._audit_format_field_list(
                    fields_to_export)
        except Exception:
            _logger.warning(
                "data_export_audit_log: could not record export of %s "
                "(%d records) by uid %s; the export itself proceeds",
                self._name, len(self), self.env.uid, exc_info=True)

    def _audit_format_field_list(self, fields_to_export):
        """Normalise the raw field argument into a capped display string."""
        paths = list(fields_to_export or [])
        # 19.0 grouped exports prepend a '.id' column the user never picked
        if paths and paths[0] == '.id':
            paths = paths[1:]
        parts = []
        for path in paths:
            # export_data also accepts pre-split path lists
            if isinstance(path, (list, tuple)):
                parts.append('/'.join(str(p) for p in path))
            else:
                parts.append(str(path))
        field_list = ', '.join(parts)
        if len(field_list) > FIELD_LIST_MAX_CHARS:
            field_list = field_list[:FIELD_LIST_MAX_CHARS - 3] + '...'
        return field_list
