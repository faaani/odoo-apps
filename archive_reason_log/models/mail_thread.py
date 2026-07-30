# -*- coding: utf-8 -*-
# Part of archive_reason_log. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

#: set by this module's wizard while it archives, so the companion module
#: ``archive_audit_trail`` (if it is installed) does not post its own, poorer
#: "Record archived." note next to the detailed one posted here.
SKIP_AUDIT_CTX = 'archive_reason_log_skip_audit'


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    # Deliberately plain text columns rather than a Many2one: these fields land
    # on every model that has a chatter, and a relational field would add a
    # foreign key - which PostgreSQL validates with a full table scan under an
    # exclusive lock - to each of those tables at install time. A name snapshot
    # costs a metadata-only ADD COLUMN and keeps reading even if the reason is
    # renamed or deleted later. archive.reason.log holds the relational history.
    archive_reason = fields.Char(
        string='Archive Reason', copy=False, readonly=True,
        help='Reason given the last time this record was archived. Cleared when '
             'the record is restored; the full history stays in the archive log.')
    archive_reason_note = fields.Text(
        string='Archive Explanation', copy=False, readonly=True,
        help='Free-text explanation given when this record was archived.')

    def _archive_audit_enabled(self):
        """Hook of the companion module ``archive_audit_trail``.

        That module logs every archive/restore with a plain note. When this
        module archives a record it posts a richer note (reason + explanation),
        so the plain one is suppressed for that single write and the event is
        never written twice. Every archive done outside this wizard is still
        logged by the companion module exactly as before.
        """
        if self.env.context.get(SKIP_AUDIT_CTX):
            return False
        parent = getattr(super(), '_archive_audit_enabled', None)
        return parent() if parent is not None else False

    def write(self, vals):
        res = super().write(vals)
        if vals.get('active'):
            # The log - not the column above - is the source of truth: a record
            # whose archive_reason was cleared out of band (data import, custom
            # script) must still close its open log entry when it comes back.
            # A savepoint keeps this bookkeeping from ever breaking a restore.
            try:
                with self.env.cr.savepoint():
                    self.env['archive.reason.log']._mark_restored(self)
                    flagged = self.filtered('archive_reason')
                    if flagged:
                        flagged.write({
                            'archive_reason': False,
                            'archive_reason_note': False,
                        })
            except Exception:  # noqa: BLE001 - bookkeeping must not break a restore
                _logger.exception(
                    'archive_reason_log: could not close the archive log of %s.',
                    self._name)
        return res
