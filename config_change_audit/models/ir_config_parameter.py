# -*- coding: utf-8 -*-
# Part of config_change_audit. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import api, models

from .config_change_audit import AUDITED_ALWAYS

_logger = logging.getLogger(__name__)


class IrConfigParameter(models.Model):
    """Record every create / write / unlink of a system parameter.

    Three rules govern every method below:

    * the old value is read BEFORE ``super()`` — afterwards it is gone;
    * the audit row is written only AFTER ``super()`` succeeded, so a refused
      change never leaves a row claiming it happened;
    * nothing here may raise. A broken audit trail is a problem; a broken audit
      trail that also blocks configuration changes is an outage.
    """
    _inherit = 'ir.config_parameter'

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _config_audit_snapshot(self):
        """{id: (key, value)} as it stands right now. Never raises."""
        try:
            return {record.id: (record.key, record.value) for record in self}
        except Exception:  # noqa: BLE001 — auditing must never block a change
            _logger.exception('config_change_audit: could not read the values '
                              'about to change; they will not be recorded')
            return {}

    @api.model
    def _config_audit_context(self):
        """Return (audit model, secret patterns, auditing enabled).

        The audit model is None when the registry does not hold it yet, which
        happens while the module itself is being installed.
        """
        if 'config.change.audit' not in self.env:
            return None, (), False
        audit = self.env['config.change.audit']
        settings = audit._config_audit_settings()
        return audit, settings['secret_patterns'], settings['enabled']

    @api.model
    def _config_audit_skip(self, enabled, *keys):
        """True when this one parameter must not be recorded.

        Changes to the module's own parameters are recorded even while auditing
        is switched off, so the trail can never be turned off silently. The
        decision is taken per parameter: a batch that happens to contain one of
        those keys must not drag every other parameter of the batch into the log.
        """
        if enabled:
            return False
        return not any(key in AUDITED_ALWAYS for key in keys if key)

    # ------------------------------------------------------------------
    # audited writes
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super(IrConfigParameter, self).create(vals_list)
        try:
            audit, patterns, enabled = self._config_audit_context()
            if audit is not None:
                audit._config_audit_record([
                    audit._config_audit_prepare(
                        'create', record.key, None, record.value, patterns=patterns)
                    for record in records
                    if not self._config_audit_skip(enabled, record.key)
                ])
        except Exception:  # noqa: BLE001 — auditing must never block a change
            _logger.exception('config_change_audit: creation of %s system '
                              'parameter(s) was not recorded', len(records))
        return records

    def write(self, vals):
        # Only key/value changes are configuration changes worth a row.
        audited = 'value' in vals or 'key' in vals
        before = self._config_audit_snapshot() if audited else {}
        result = super(IrConfigParameter, self).write(vals)
        if not before:
            return result
        try:
            audit, patterns, enabled = self._config_audit_context()
            if audit is None:
                return result
            rows = []
            for record in self:
                old_key, old_value = before.get(record.id, (False, False))
                if record.key == old_key and record.value == old_value:
                    continue  # a write that changed nothing is not a change
                if self._config_audit_skip(enabled, record.key, old_key):
                    continue
                rows.append(audit._config_audit_prepare(
                    'write', record.key, old_value, record.value,
                    previous_key=old_key if old_key != record.key else None,
                    patterns=patterns))
            audit._config_audit_record(rows)
        except Exception:  # noqa: BLE001 — auditing must never block a change
            _logger.exception('config_change_audit: a system parameter change '
                              'was not recorded')
        return result

    def unlink(self):
        before = self._config_audit_snapshot()
        result = super(IrConfigParameter, self).unlink()
        try:
            audit, patterns, enabled = self._config_audit_context()
            if audit is not None:
                audit._config_audit_record([
                    audit._config_audit_prepare(
                        'unlink', key, value, None, patterns=patterns)
                    for key, value in before.values()
                    if not self._config_audit_skip(enabled, key)
                ])
        except Exception:  # noqa: BLE001 — auditing must never block a change
            _logger.exception('config_change_audit: deletion of %s system '
                              'parameter(s) was not recorded', len(before))
        return result
