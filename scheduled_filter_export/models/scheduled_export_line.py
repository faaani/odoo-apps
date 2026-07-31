# -*- coding: utf-8 -*-
# Part of scheduled_filter_export. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

#: Field types that cannot be written into a spreadsheet cell in any useful
#: way. Binary columns would turn a small list into a multi-megabyte file of
#: base64 noise, so they are simply not offered.
UNSUPPORTED_TTYPES = ('binary',)


class ScheduledExportLine(models.Model):
    _name = 'scheduled.export.line'
    _description = 'Scheduled Export Column'
    _order = 'sequence, id'

    export_id = fields.Many2one(
        'scheduled.export',
        string='Export',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(
        default=10,
        help='Column order in the generated file: drag the lines to reorder.',
    )
    field_id = fields.Many2one(
        'ir.model.fields',
        string='Field',
        required=True,
        ondelete='cascade',
        help='The field exported in this column. It must belong to the model '
             'selected on the export.',
    )
    field_name = fields.Char(
        related='field_id.name',
        string='Technical Name',
        store=True,
        readonly=True,
    )
    ttype = fields.Selection(
        related='field_id.ttype',
        string='Type',
        readonly=True,
    )
    label = fields.Char(
        string='Column Heading',
        help='Heading written in the file for this column. Leave empty to use '
             'the field label as translated for the user the export runs as.',
    )

    @api.constrains('field_id', 'export_id')
    def _check_field_belongs_to_model(self):
        for line in self:
            model = line.export_id.model_id
            if model and line.field_id.model_id != model:
                raise ValidationError(_(
                    'The column "%(field)s" belongs to %(field_model)s, but the '
                    'export "%(export)s" is about %(export_model)s. Pick a '
                    'field of the exported model.'
                ) % {
                    'field': line.field_id.name or '',
                    'field_model': line.field_id.model_id.model or '?',
                    'export': line.export_id.name or '',
                    'export_model': model.model,
                })
            if line.field_id.ttype in UNSUPPORTED_TTYPES:
                raise ValidationError(_(
                    'The field "%s" holds a file and cannot be written into a '
                    'CSV or Excel column.'
                ) % (line.field_id.name or ''))

    @api.constrains('export_id', 'field_id')
    def _check_field_not_duplicated(self):
        for line in self:
            if not line.export_id or not line.field_id:
                continue
            twins = line.export_id.line_ids.filtered(
                lambda other, line=line: other.field_id == line.field_id
                and other.id != line.id)
            if twins:
                raise ValidationError(_(
                    'The field "%s" is already one of the columns of this '
                    'export.'
                ) % (line.field_id.name or ''))

    def _column_label(self, descriptions):
        """Heading for this column: the override if the user typed one, else
        the field label as the run-as user sees it."""
        self.ensure_one()
        if self.label:
            return self.label
        description = descriptions.get(self.field_id.name) or {}
        return description.get('string') or self.field_id.name
