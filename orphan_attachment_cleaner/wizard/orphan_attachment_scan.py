# -*- coding: utf-8 -*-
# Part of orphan_attachment_cleaner. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Attachments on these models are web assets or module data. Odoo creates and
# regenerates them on its own, so they are never orphans and never deleted.
PROTECTED_MODELS = [
    'ir.ui.view',
    'ir.asset',
    'ir.actions.report',
    'ir.module.module',
]

REASON_MISSING_MODEL = 'missing_model'
REASON_MISSING_RECORD = 'missing_record'


def format_size(num_bytes):
    """Return a byte count as a short human readable string."""
    size = float(num_bytes or 0)
    if size < 1024:
        return _('%s bytes') % int(size)
    for unit in ('KB', 'MB', 'GB'):
        size /= 1024.0
        if size < 1024:
            return '%.2f %s' % (size, unit)
    return '%.2f TB' % (size / 1024.0)


class OrphanAttachmentScan(models.TransientModel):
    _name = 'orphan.attachment.scan'
    _description = 'Orphaned Attachment Scan'

    line_ids = fields.One2many(
        'orphan.attachment.scan.line', 'scan_id', string='Orphaned Attachments')
    inspected_count = fields.Integer(string='Attachments Inspected', readonly=True)
    orphan_count = fields.Integer(
        string='Orphans Found', compute='_compute_totals')
    reclaimable_size = fields.Float(
        string='Reclaimable Space (bytes)', compute='_compute_totals')
    reclaimable_size_display = fields.Char(
        string='Reclaimable Space', compute='_compute_totals')
    summary_note = fields.Char(string='Result', compute='_compute_totals')
    confirmed = fields.Boolean(
        string='Yes, permanently delete the selected files')

    @api.depends('line_ids.attachment_count', 'line_ids.total_size', 'inspected_count')
    def _compute_totals(self):
        for scan in self:
            count = sum(scan.line_ids.mapped('attachment_count'))
            size = sum(scan.line_ids.mapped('total_size'))
            scan.orphan_count = count
            scan.reclaimable_size = size
            scan.reclaimable_size_display = format_size(size)
            if count:
                scan.summary_note = _(
                    '%(orphans)s orphaned attachment(s) in %(groups)s model(s) — '
                    '%(size)s can be reclaimed. Nothing has been deleted yet.'
                ) % {
                    'orphans': count,
                    'groups': len(scan.line_ids),
                    'size': format_size(size),
                }
            else:
                scan.summary_note = _(
                    'No orphaned attachments found — %s attachment(s) inspected.'
                ) % scan.inspected_count

    @api.model
    def default_get(self, fields_list):
        res = super(OrphanAttachmentScan, self).default_get(fields_list)
        if 'line_ids' in fields_list or 'inspected_count' in fields_list:
            values, inspected = self._collect_orphans()
            res['line_ids'] = [(0, 0, vals) for vals in values]
            res['inspected_count'] = inspected
        return res

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------
    @api.model
    def _protected_models(self):
        """Models whose attachments are assets/module data and are never touched."""
        return list(PROTECTED_MODELS)

    @api.model
    def _scan_domain(self):
        """Attachments the scan is allowed to look at.

        Excluded on purpose, and never reported nor deleted:
          * ``res_model`` empty — free-standing files a user uploaded on their own;
          * ``res_field`` set — the storage behind a binary field, deleting it
            would blank the field on a perfectly live record;
          * asset and module-data models — Odoo owns and regenerates those.
        """
        return [
            ('res_model', '!=', False),
            ('res_field', '=', False),
            ('res_model', 'not in', self._protected_models()),
        ]

    @api.model
    def _collect_orphans(self):
        """Return ``(line values, number of attachments inspected)``.

        One grouped query lists every model that owns attachments, then each
        model costs one grouped query for its record ids plus one existence
        check — attachments are never browsed one by one.
        """
        attachment = self.env['ir.attachment'].sudo()
        domain = self._scan_domain()
        inspected = attachment.search_count(domain)
        groups = attachment.read_group(domain, ['file_size'], ['res_model'], lazy=False)
        values = []
        for group in groups:
            res_model = group.get('res_model')
            if not res_model:
                continue
            if res_model not in self.env:
                # the model itself is gone from the registry: every attachment
                # of that group points into nothing
                attachments = attachment.search(domain + [('res_model', '=', res_model)])
                if attachments:
                    values.append(self._prepare_line(
                        res_model, REASON_MISSING_MODEL, attachments,
                        group.get('file_size') or 0.0))
                continue
            target = self.env[res_model].sudo()
            if target._abstract:
                # an abstract model has no table to check against — never guess
                continue
            # res_id <= 0 means "not attached to a record yet" (an upload in
            # progress), which is not an orphan
            model_domain = domain + [('res_model', '=', res_model), ('res_id', '>', 0)]
            # one grouped query per model: the distinct record ids it points at
            id_groups = attachment.read_group(
                model_domain, ['file_size'], ['res_id'], lazy=False)
            sizes = {}
            for id_group in id_groups:
                res_id = id_group.get('res_id')
                if res_id:
                    sizes[res_id] = id_group.get('file_size') or 0.0
            if not sizes:
                continue
            res_ids = sorted(sizes)
            try:
                # exists() is a single "SELECT id FROM <table> WHERE id IN %s".
                # It ignores record rules and the active flag, so a record that
                # is merely archived or invisible to the current user is never
                # mistaken for a deleted one — and an empty model simply
                # returns nothing rather than raising.
                existing = set(target.browse(res_ids).exists().ids)
            except Exception:  # noqa: BLE001 - unqueryable model must not abort the scan
                _logger.warning(
                    'Orphaned attachment scan: skipping %s, its records could '
                    'not be checked.', res_model)
                continue
            missing = [res_id for res_id in res_ids if res_id not in existing]
            if not missing:
                continue
            attachments = attachment.search(model_domain + [('res_id', 'in', missing)])
            if attachments:
                values.append(self._prepare_line(
                    res_model, REASON_MISSING_RECORD, attachments,
                    sum(sizes[res_id] for res_id in missing)))
        return values, inspected

    @api.model
    def _prepare_line(self, res_model, reason, attachments, total_size):
        return {
            'res_model': res_model,
            'reason': reason,
            'attachment_count': len(attachments),
            'total_size': total_size,
            'attachment_ids': [(6, 0, attachments.ids)],
        }

    def action_scan(self):
        """Re-run the scan on this wizard. Read only: nothing is deleted."""
        self.ensure_one()
        self.line_ids.unlink()
        values, inspected = self._collect_orphans()
        self.write({
            'line_ids': [(0, 0, vals) for vals in values],
            'inspected_count': inspected,
            'confirmed': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def action_cleanup(self):
        """Delete the reported attachments. Settings administrators only."""
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_(
                'Only Settings administrators may delete orphaned attachments.'))
        if not self.confirmed:
            raise UserError(_(
                'Tick the confirmation box first: deleted attachments and their '
                'files cannot be recovered.'))
        lines = self.line_ids.filtered(lambda line: line.to_clean)
        if not lines:
            raise UserError(_('Select at least one line to delete.'))
        attachments = lines.sudo().mapped('attachment_ids')
        # last safety net: re-apply the exclusions to whatever is still there,
        # so nothing outside the reported set can ever be removed
        protected = self._protected_models()
        attachments = attachments.filtered(
            lambda att: att.res_model and not att.res_field
            and att.res_model not in protected)
        if not attachments:
            raise UserError(_('The selected attachments no longer exist.'))
        removed = len(attachments)
        freed = sum(attachments.mapped('file_size'))
        attachments.unlink()
        _logger.info(
            'Orphaned attachment cleanup by %s: %s attachment(s) deleted, %s freed.',
            self.env.user.login, removed, format_size(freed))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Orphaned attachments deleted'),
                'message': _('%(count)s attachment(s) removed, %(size)s reclaimed.') % {
                    'count': removed, 'size': format_size(freed)},
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class OrphanAttachmentScanLine(models.TransientModel):
    _name = 'orphan.attachment.scan.line'
    _description = 'Orphaned Attachment Group'
    _order = 'total_size desc, res_model'

    scan_id = fields.Many2one(
        'orphan.attachment.scan', string='Scan', required=True, ondelete='cascade')
    res_model = fields.Char(string='Model', readonly=True)
    reason = fields.Selection(
        [(REASON_MISSING_MODEL, 'Model no longer exists'),
         (REASON_MISSING_RECORD, 'Record no longer exists')],
        string='Reason', readonly=True)
    attachment_count = fields.Integer(string='Attachments', readonly=True)
    total_size = fields.Float(string='Space (bytes)', readonly=True)
    size_display = fields.Char(string='Reclaimable Space', compute='_compute_size_display')
    to_clean = fields.Boolean(string='Delete', default=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Orphaned Files')

    @api.depends('total_size')
    def _compute_size_display(self):
        for line in self:
            line.size_display = format_size(line.total_size)

    @api.model_create_multi
    def create(self, vals_list):
        # ir.attachment checks access against the record an attachment points
        # at, so the attachments of a deleted record can be unreadable even for
        # an administrator. The link is therefore written with elevated rights;
        # it is never exposed in the interface, and action_cleanup still checks
        # the user's group before deleting anything.
        attachments, cleaned = [], []
        for vals in vals_list:
            vals = dict(vals)
            attachments.append(vals.pop('attachment_ids', False))
            cleaned.append(vals)
        lines = super(OrphanAttachmentScanLine, self).create(cleaned)
        for line, commands in zip(lines, attachments):
            if commands:
                line.sudo().write({'attachment_ids': commands})
        return lines
