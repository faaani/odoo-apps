# -*- coding: utf-8 -*-
# Part of config_change_audit. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
from datetime import timedelta

from odoo import api, fields, models, SUPERUSER_ID
from odoo.http import request
from odoo.tools import str2bool

_logger = logging.getLogger(__name__)

PARAM_ENABLED = 'config_change_audit.enabled'
PARAM_RETENTION = 'config_change_audit.retention_days'
PARAM_SECRET_PATTERNS = 'config_change_audit.secret_patterns'
# Changes to these three keys are recorded even while auditing is switched off,
# so switching it off (or widening the masking rules) can never be done silently.
AUDITED_ALWAYS = (PARAM_ENABLED, PARAM_RETENTION, PARAM_SECRET_PATTERNS)

DEFAULT_SECRET_PATTERNS = 'key,secret,token,password'
DEFAULT_RETENTION_DAYS = 365
# ir.config_parameter.get_param() returns the DEFAULT for any falsy stored
# value, so "mask nothing" cannot be stored as an empty string — it is kept as
# this sentinel instead. It is deliberately not a word anybody would type as a
# pattern: a plain "none" must stay a literal pattern, not a silent kill switch.
NO_SECRET_SENTINEL = '__none__'
# What a masked value is stored as. The real value never reaches this table.
MASKED_PLACEHOLDER = '********'
# Values longer than this are stored truncated (and flagged as such): a single
# parameter can legitimately hold a whole certificate or JSON blob, and an audit
# table is not a place to duplicate them.
MAX_STORED_VALUE = 512
# A parameter can hold a certificate or a JSON blob: the list shows a one-line
# preview of that length, the row itself keeps the stored value in full.
PREVIEW_LENGTH = 80
# Retention clean-up: rows are deleted in batches, with a ceiling per run so a
# first run on a huge backlog cannot hold a transaction open for ever.
GC_BATCH_SIZE = 1000
GC_MAX_PER_RUN = 100000


class ConfigChangeAudit(models.Model):
    _name = 'config.change.audit'
    _description = 'System Parameter Change'
    _order = 'change_date desc, id desc'
    _rec_name = 'key'

    key = fields.Char(
        string='Parameter', required=True, index=True, readonly=True,
        help='Key of the system parameter as it stands after the change.',
    )
    previous_key = fields.Char(
        string='Previous Key', readonly=True,
        help='Filled only when the change renamed the parameter key.',
    )
    operation = fields.Selection(
        [('create', 'Created'), ('write', 'Updated'), ('unlink', 'Deleted')],
        string='Operation', required=True, index=True, readonly=True,
    )
    old_value = fields.Text(
        string='Old Value (full)', readonly=True,
        help='Value before the change. Empty when the parameter was created.',
    )
    new_value = fields.Text(
        string='New Value (full)', readonly=True,
        help='Value after the change. Empty when the parameter was deleted.',
    )
    old_value_preview = fields.Char(
        string='Old Value', compute='_compute_value_preview',
        help='The old value on a single line, shortened to %s characters for the '
             'list. Open the row to read it in full.' % PREVIEW_LENGTH,
    )
    new_value_preview = fields.Char(
        string='New Value', compute='_compute_value_preview',
        help='The new value on a single line, shortened to %s characters for the '
             'list. Open the row to read it in full.' % PREVIEW_LENGTH,
    )
    is_masked = fields.Boolean(
        string='Masked', readonly=True,
        help='The key looks like a secret (API key, token, password), so the '
             'values are stored as %s instead of the real content.' % MASKED_PLACEHOLDER,
    )
    is_truncated = fields.Boolean(
        string='Truncated', readonly=True,
        help='At least one of the two values was longer than %s characters and '
             'is stored cut down to its first %s characters.'
             % (MAX_STORED_VALUE, MAX_STORED_VALUE),
    )
    user_id = fields.Many2one(
        'res.users', string='Changed By', index=True, readonly=True,
        help='User who made the change. Changes made by scheduled actions, by '
             'the command line or during a module installation are recorded as '
             'OdooBot. Empty only if the user account was deleted afterwards.',
    )
    change_date = fields.Datetime(
        string='Changed On', required=True, index=True, readonly=True,
        default=fields.Datetime.now,
    )

    @api.depends('old_value', 'new_value')
    def _compute_value_preview(self):
        for record in self:
            record.old_value_preview = self._config_audit_preview(record.old_value)
            record.new_value_preview = self._config_audit_preview(record.new_value)

    @api.model
    def _config_audit_preview(self, value):
        """One-line, list-sized rendering of a stored value."""
        if not value:
            return value
        flat = ' '.join(value.split())
        if len(flat) <= PREVIEW_LENGTH:
            return flat
        return flat[:PREVIEW_LENGTH - 1] + '…'

    # ------------------------------------------------------------------
    # settings
    # ------------------------------------------------------------------
    @api.model
    def _config_audit_settings(self):
        """Read the module settings. Falsy stored values are handled explicitly."""
        icp = self.env['ir.config_parameter'].sudo()
        try:
            enabled = str2bool(icp.get_param(PARAM_ENABLED, 'True'))
        except ValueError:
            enabled = True
        try:
            retention = int(icp.get_param(PARAM_RETENTION, DEFAULT_RETENTION_DAYS))
        except (TypeError, ValueError):
            retention = DEFAULT_RETENTION_DAYS
        raw = icp.get_param(PARAM_SECRET_PATTERNS, DEFAULT_SECRET_PATTERNS) or ''
        if raw.strip().lower() == NO_SECRET_SENTINEL:
            raw = ''
        patterns = tuple(p.strip().lower() for p in raw.split(',') if p.strip())
        return {
            'enabled': enabled,
            'retention_days': max(retention, 0),
            'secret_patterns': patterns,
        }

    # ------------------------------------------------------------------
    # value handling
    # ------------------------------------------------------------------
    @api.model
    def _config_audit_is_secret(self, key, patterns):
        """True when the key looks like it holds a credential."""
        low = (key or '').lower()
        return any(pattern in low for pattern in patterns)

    @api.model
    def _config_audit_store(self, value, masked):
        """Return (stored value, truncated?) for one side of a change."""
        if value is None or value is False:
            return False, False
        text = value if isinstance(value, str) else str(value)
        if masked:
            return MASKED_PLACEHOLDER, False
        if len(text) > MAX_STORED_VALUE:
            return text[:MAX_STORED_VALUE], True
        return text, False

    @api.model
    def _config_audit_actor(self):
        """Id of the user responsible for the change.

        ``sudo()`` does not change ``env.uid`` — it only bypasses access rights —
        so a parameter written through ``sudo()`` is already attributed to the
        real user. This fallback covers the other case: code that genuinely runs
        as OdooBot (``with_user(SUPERUSER_ID)``) inside a web request. There the
        logged-in user of that request is the person responsible, so it is
        preferred over the superuser. Crons and the command line have no request
        and stay attributed to OdooBot, which is the truth.
        """
        uid = self.env.uid
        if uid == SUPERUSER_ID:
            try:
                if request and request.session and request.session.uid:
                    uid = request.session.uid
            except Exception:  # noqa: BLE001 — no usable request, keep OdooBot
                pass
        return uid

    @api.model
    def _config_audit_prepare(self, operation, key, old_value, new_value,
                              previous_key=None, patterns=()):
        """Build the values of one audit row (masking and truncation applied)."""
        # The module's own settings are configuration, not credentials: one of
        # them contains "secret" in its name, and masking it would hide exactly
        # the change that weakens the masking rules.
        masked = key not in AUDITED_ALWAYS and (
            self._config_audit_is_secret(key, patterns)
            or self._config_audit_is_secret(previous_key, patterns))
        stored_old, old_cut = self._config_audit_store(old_value, masked)
        stored_new, new_cut = self._config_audit_store(new_value, masked)
        return {
            'key': key,
            'previous_key': previous_key or False,
            'operation': operation,
            'old_value': stored_old,
            'new_value': stored_new,
            'is_masked': masked,
            'is_truncated': old_cut or new_cut,
            'user_id': self._config_audit_actor(),
            'change_date': fields.Datetime.now(),
        }

    @api.model
    def _config_audit_record(self, rows):
        """Write audit rows without ever breaking the change being audited.

        The savepoint matters as much as the try/except: a failed INSERT aborts
        the whole PostgreSQL transaction, which would take the configuration
        change down with it even though the exception was caught.
        """
        if not rows:
            return self.browse()
        try:
            with self.env.cr.savepoint():
                # The single write point of an append-only log. Nobody holds
                # create rights on the model, so an administrator cannot forge
                # or back-date a row over RPC; this sudo() therefore narrows
                # what is reachable by hand instead of widening it, and it also
                # covers changes made by code running as a non-administrator.
                return self.sudo().create(rows)
        except Exception:  # noqa: BLE001 — auditing must never block a change
            _logger.exception(
                'config_change_audit: could not record %s system parameter '
                'change(s): %s', len(rows), ', '.join(r.get('key') or '?' for r in rows))
        return self.browse()

    # ------------------------------------------------------------------
    # retention
    # ------------------------------------------------------------------
    @api.model
    def _gc_audit_log(self):
        """Delete audit rows older than the retention window (0 = keep for ever)."""
        days = self._config_audit_settings()['retention_days']
        if not days:
            _logger.info('config_change_audit: retention disabled, nothing removed')
            return 0
        cutoff = fields.Datetime.now() - timedelta(days=days)
        removed = 0
        while removed < GC_MAX_PER_RUN:
            batch = self.search([('change_date', '<', cutoff)], limit=GC_BATCH_SIZE)
            if not batch:
                break
            removed += len(batch)
            batch.unlink()
        if removed >= GC_MAX_PER_RUN:
            _logger.warning(
                'config_change_audit: stopped after %s rows; the next daily run '
                'continues with the rest', removed)
        elif removed:
            _logger.info('config_change_audit: removed %s row(s) older than %s days',
                         removed, days)
        return removed
