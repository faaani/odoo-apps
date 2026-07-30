# -*- coding: utf-8 -*-
# Part of sequence_gap_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import re

from odoo import _, fields, models
from odoo.exceptions import UserError

# Longest run of trailing digits: 'INV/2026/00042' -> ('INV/2026/', '00042').
# The prefix part is deliberately unconstrained: no numbering format is assumed.
TRAILING_NUMBER = re.compile(r'^(.*?)(\d+)\Z')

# Hard ceiling on the number of reported gaps, whatever the user asks for:
# a badly chosen model must never fill the database with report lines.
ABSOLUTE_MAX_GAPS = 5000

# Hard ceiling on the number of scanned values: the column is read in one go,
# so a model with millions of rows is refused instead of eating the worker.
ABSOLUTE_MAX_ROWS = 200000

# A hole wider than this is not a numbering gap but two unrelated series that
# happen to share a prefix (barcodes, VAT or legacy references).
MAX_GAP_SPAN = 1000000

# Reported numbers live in integer columns.
INT4_MAX = 2147483647


class SequenceGapReport(models.TransientModel):
    _name = 'sequence.gap.report'
    _description = 'Sequence Gap Report'

    model_name = fields.Char(
        string='Model', required=True, default='account.move',
        help="Technical name of the model to scan, for example account.move "
             "(invoices and journal entries), sale.order, purchase.order or "
             "stock.picking.")
    field_name = fields.Char(
        string='Numbered Field', required=True, default='name',
        help="Stored text field holding the sequence number, usually 'name'.")
    include_archived = fields.Boolean(
        string='Include Archived', default=True,
        help="Archived documents still consumed a number, so they count as "
             "present by default. Untick to scan active documents only.")
    max_gaps = fields.Integer(
        string='Maximum Gaps', required=True, default=500,
        help="Safety cap on the number of gaps listed. The report says so when "
             "more gaps than this exist.")
    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Done')], default='draft', required=True)
    summary = fields.Char(string='Result', readonly=True)
    truncated = fields.Boolean(string='Truncated', readonly=True)
    truncation_note = fields.Char(string='Truncation Note', readonly=True)
    line_ids = fields.One2many(
        'sequence.gap.line', 'report_id', string='Gaps', readonly=True)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _get_scan_target(self):
        """Validate the user input and return (recordset, field name)."""
        self.ensure_one()
        model_name = (self.model_name or '').strip()
        field_name = (self.field_name or '').strip()
        if not model_name or model_name not in self.env:
            raise UserError(_(
                'There is no model called "%s" in this database. Install the '
                'application that provides it, or scan another model such as '
                'sale.order, purchase.order or stock.picking.') % model_name)
        model = self.env[model_name]
        if model._abstract or model._transient:
            raise UserError(_(
                '"%s" does not store documents, so it has no numbering to '
                'check.') % model_name)
        field = model._fields.get(field_name)
        if field is None:
            raise UserError(_(
                'There is no field called "%(field)s" on "%(model)s".') % {
                    'field': field_name, 'model': model_name})
        if not field.store or field.type not in ('char', 'text'):
            raise UserError(_(
                'The field "%(field)s" of "%(model)s" is not a stored text '
                'field, so it cannot hold a sequence number.') % {
                    'field': field_name, 'model': model_name})
        return model, field_name

    @staticmethod
    def _group_by_prefix(rows, field_name):
        """Split every value into prefix + trailing number, grouped by prefix.

        Returns ({prefix: {number: (value, width)}}, count of ignored values).
        """
        series = {}
        ignored = 0
        for row in rows:
            value = (row.get(field_name) or '').strip()
            match = TRAILING_NUMBER.match(value) if value else None
            if not match:
                ignored += 1
                continue
            prefix, digits = match.group(1), match.group(2)
            # duplicates keep the first value seen; a duplicate is not a gap
            series.setdefault(prefix, {}).setdefault(
                int(digits), (value, len(digits)))
        return series, ignored

    @staticmethod
    def _find_gaps(series):
        """Return (gaps, skipped) for the missing ranges of each prefix.

        Holes wider than MAX_GAP_SPAN, or whose numbers do not fit in an
        integer column, are not numbering gaps: they are counted apart so the
        summary can say how many were left out.
        """
        gaps = []
        skipped = 0
        for prefix in sorted(series):
            entries = series[prefix]
            numbers = sorted(entries)
            for lower, upper in zip(numbers, numbers[1:]):
                if upper - lower <= 1:
                    continue
                if upper > INT4_MAX or upper - lower - 1 > MAX_GAP_SPAN:
                    skipped += 1
                    continue
                previous_value, previous_width = entries[lower]
                next_value, next_width = entries[upper]
                # pad the missing numbers like their neighbours are padded
                width = max(previous_width, next_width)
                gaps.append({
                    'prefix': prefix,
                    'first_number': lower + 1,
                    'first_missing': prefix + str(lower + 1).zfill(width),
                    'last_missing': prefix + str(upper - 1).zfill(width),
                    'missing_count': upper - lower - 1,
                    'previous_value': previous_value,
                    'next_value': next_value,
                })
        return gaps, skipped

    def _scan_context(self):
        """Scan every company the user may access, not only the ticked ones."""
        self.ensure_one()
        context = {'active_test': not self.include_archived}
        companies = self.env.user.company_ids.ids
        if companies:
            context['allowed_company_ids'] = companies
        return context

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sequence Gap Report'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context),
        }

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def action_scan(self):
        """Read the numbered column once and report the holes it contains."""
        self.ensure_one()
        model, field_name = self._get_scan_target()
        max_gaps = min(max(self.max_gaps or 0, 1), ABSOLUTE_MAX_GAPS)

        # one single read of one single column; access rights still apply
        rows = model.with_context(**self._scan_context()).search_read(
            [(field_name, '!=', False)], [field_name],
            limit=ABSOLUTE_MAX_ROWS + 1, order='id')
        if len(rows) > ABSOLUTE_MAX_ROWS:
            # scanning fewer rows than exist would invent gaps: refuse instead
            raise UserError(_(
                '"%(model)s" holds more than %(cap)s numbered documents. '
                'Scan a narrower model, or a field with fewer values.') % {
                    'model': model._name, 'cap': ABSOLUTE_MAX_ROWS})
        series, ignored = self._group_by_prefix(rows, field_name)
        gaps, skipped = self._find_gaps(series)

        self.line_ids.unlink()
        self.env['sequence.gap.line'].create([
            dict(vals, report_id=self.id) for vals in gaps[:max_gaps]])

        missing = sum(gap['missing_count'] for gap in gaps)
        truncated = len(gaps) > max_gaps
        note = False
        if truncated and (self.max_gaps or 0) > ABSOLUTE_MAX_GAPS:
            note = _(
                'Maximum Gaps was capped at %(cap)s: only the first %(kept)s '
                'gaps out of %(total)s are listed. Scan a narrower model to '
                'see the rest.') % {
                    'kept': max_gaps, 'total': len(gaps),
                    'cap': ABSOLUTE_MAX_GAPS}
        elif truncated:
            note = _(
                'Only the first %(kept)s gaps out of %(total)s are listed. '
                'Raise "Maximum Gaps" (up to %(cap)s) or scan a narrower '
                'model to see the rest.') % {
                    'kept': max_gaps, 'total': len(gaps),
                    'cap': ABSOLUTE_MAX_GAPS}
        parts = [_(
            'Scanned %(scanned)s document(s) in %(series)s numbering series: '
            '%(gaps)s gap(s) covering %(missing)s missing number(s). '
            '%(ignored)s value(s) without a trailing number were ignored.') % {
                'scanned': len(rows), 'series': len(series),
                'gaps': len(gaps), 'missing': missing, 'ignored': ignored}]
        if skipped:
            parts.append(_(
                '%(skipped)s hole(s) wider than %(span)s numbers were skipped '
                'as implausible.') % {'skipped': skipped, 'span': MAX_GAP_SPAN})
        parts.append(_(
            'Only documents you are allowed to read are counted, so numbers '
            'hidden by access rights appear here as gaps.'))
        summary = ' '.join(parts)
        self.write({
            'state': 'done',
            'truncated': truncated,
            'summary': summary,
            'truncation_note': note,
        })
        return self._reopen()

    def action_reset(self):
        """Clear the result and go back to the scan parameters."""
        self.ensure_one()
        self.line_ids.unlink()
        self.write({
            'state': 'draft',
            'summary': False,
            'truncated': False,
            'truncation_note': False,
        })
        return self._reopen()

    def action_open_lines(self):
        """Open the gaps in a full list view, so they can be sorted/exported."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'sequence_gap_report.action_sequence_gap_line')
        action['domain'] = [('report_id', '=', self.id)]
        action['context'] = {'create': False, 'edit': False, 'delete': False}
        return action


class SequenceGapLine(models.TransientModel):
    _name = 'sequence.gap.line'
    _description = 'Sequence Gap'
    _order = 'prefix, first_number'
    _rec_name = 'first_missing'

    report_id = fields.Many2one(
        'sequence.gap.report', string='Report', required=True,
        ondelete='cascade', index=True)
    prefix = fields.Char(string='Series Prefix', readonly=True)
    first_number = fields.Integer(string='First Missing Number', readonly=True)
    first_missing = fields.Char(string='Missing From', readonly=True)
    last_missing = fields.Char(string='Missing To', readonly=True)
    missing_count = fields.Integer(string='Missing Numbers', readonly=True)
    previous_value = fields.Char(string='Document Before', readonly=True)
    next_value = fields.Char(string='Document After', readonly=True)
