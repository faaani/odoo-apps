# -*- coding: utf-8 -*-
# Part of attachment_storage_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

MB = 1024.0 * 1024.0
# Grouped results are already tiny (one row per model / per user); the cap only
# protects the form view of pathological databases.
GROUP_LIMIT = 200
MAX_TOP_LIMIT = 1000


def format_size(num_bytes):
    """Return a human readable size, e.g. 1.44 MB."""
    num = float(num_bytes or 0)
    if num < 1024.0:
        return '%d B' % int(num)
    for unit in ('KB', 'MB', 'GB'):
        num /= 1024.0
        if abs(num) < 1024.0:
            return '%.2f %s' % (num, unit)
    return '%.2f TB' % (num / 1024.0)


class AttachmentStorageReport(models.TransientModel):
    _name = 'attachment.storage.report'
    _description = 'Attachment Storage Report'

    # keeps the breadcrumb readable instead of "attachment.storage.report,4"
    name = fields.Char(
        string='Report', readonly=True,
        default=lambda self: _('Attachment Storage Report'))
    min_size_mb = fields.Float(
        string='Minimum Size (MB)', default=0.0, digits=(16, 3),
        help='Only attachments of at least this size are counted. Raise it to '
             'ignore the thousands of tiny files and see what really uses space.')
    top_limit = fields.Integer(
        string='Largest Files to List', default=25,
        help='How many of the biggest attachments to list (1-1000).')
    date_from = fields.Datetime(
        string='Uploaded From', help='Only count attachments created on or after this moment.')
    date_to = fields.Datetime(
        string='Uploaded Until', help='Only count attachments created on or before this moment.')
    include_field_attachments = fields.Boolean(
        string='Include Field Attachments', default=True,
        help='Binary field values (company logos, product images, stored report '
             'PDFs) are attachments too. Untick to look at user uploads only.')

    total_count = fields.Integer(string='Attachments', readonly=True)
    total_size_mb = fields.Float(string='Total Size (MB)', readonly=True, digits=(16, 3))
    total_size_display = fields.Char(string='Total Size', readonly=True)
    filestore_size_display = fields.Char(string='Stored on Filestore', readonly=True)
    db_size_display = fields.Char(string='Stored in Database', readonly=True)

    model_line_ids = fields.One2many(
        'attachment.storage.report.model.line', 'report_id', string='By Model')
    user_line_ids = fields.One2many(
        'attachment.storage.report.user.line', 'report_id', string='By User')
    attachment_line_ids = fields.One2many(
        'attachment.storage.report.attachment.line', 'report_id', string='Largest Attachments')

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _check_report_access(self):
        """The report reads every attachment row in the database, so it is
        reserved to Settings administrators."""
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_(
                'Only Settings administrators may run the Attachment Storage Report.'))

    def _flush_attachments(self):
        """Make sure pending ORM writes hit the database before we query it."""
        attachment = self.env['ir.attachment']
        flush_model = getattr(attachment, 'flush_model', None)
        if flush_model:  # 17.0+
            flush_model()
        else:  # 14.0 - 16.0
            attachment.flush()

    def _where_clause(self):
        """Build the shared WHERE fragment + bound parameters for every query."""
        self.ensure_one()
        clauses = ['a.file_size >= %s']
        params = [int(max(self.min_size_mb or 0.0, 0.0) * MB)]
        if not self.include_field_attachments:
            clauses.append('a.res_field IS NULL')
        if self.date_from:
            clauses.append('a.create_date >= %s')
            params.append(self.date_from)
        if self.date_to:
            clauses.append('a.create_date <= %s')
            params.append(self.date_to)
        # multi-company: never report on companies the user is not working in
        clauses.append('(a.company_id IS NULL OR a.company_id IN %s)')
        params.append(tuple(self.env.companies.ids) or (0,))
        return ' AND '.join(clauses), params

    def _attachment_domain_extra(self):
        """Mirror the report filters in the drill-down list.

        ir.attachment._search silently prepends ('res_field', '=', False)
        unless the domain already mentions res_field, so a report that counts
        binary-field attachments must say so explicitly or the list shows far
        fewer rows than the figure the user clicked on.
        """
        self.ensure_one()
        domain = []
        if self.include_field_attachments:
            domain += ['|', ('res_field', '=', False), ('res_field', '!=', False)]
        else:
            domain.append(('res_field', '=', False))
        if self.date_from:
            domain.append(('create_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('create_date', '<=', self.date_to))
        return domain

    def _model_labels(self):
        return {m.model: m.name for m in self.env['ir.model'].sudo().search([])}

    def _existing_user_ids(self, uids):
        clean = [u for u in uids if u]
        if not clean:
            return set()
        return set(self.env['res.users'].sudo().browse(clean).exists().ids)

    # ------------------------------------------------------------------
    # report
    # ------------------------------------------------------------------
    def _compute_report(self):
        """Refresh the three breakdowns. Aggregation is done by PostgreSQL:
        no attachment is ever browsed except the handful in the top-N list."""
        self.ensure_one()
        self._check_report_access()
        self._flush_attachments()
        where, params = self._where_clause()
        limit = min(max(self.top_limit or 25, 1), MAX_TOP_LIMIT)
        cr = self.env.cr

        cr.execute("""
            SELECT COUNT(*),
                   COALESCE(SUM(a.file_size), 0),
                   COALESCE(SUM(CASE WHEN a.store_fname IS NOT NULL
                                     THEN a.file_size ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN a.db_datas IS NOT NULL
                                     THEN a.file_size ELSE 0 END), 0)
              FROM ir_attachment a
             WHERE """ + where, params)
        total_count, total_size, filestore_size, db_size = cr.fetchone()
        total_size = float(total_size or 0)

        cr.execute("""
            SELECT COALESCE(a.res_model, ''), COALESCE(SUM(a.file_size), 0), COUNT(*)
              FROM ir_attachment a
             WHERE """ + where + """
          GROUP BY COALESCE(a.res_model, '')
          ORDER BY 2 DESC
             LIMIT %s""", params + [GROUP_LIMIT])
        model_rows = cr.fetchall()

        cr.execute("""
            SELECT a.create_uid, COALESCE(SUM(a.file_size), 0), COUNT(*)
              FROM ir_attachment a
             WHERE """ + where + """
          GROUP BY a.create_uid
          ORDER BY 2 DESC
             LIMIT %s""", params + [GROUP_LIMIT])
        user_rows = cr.fetchall()

        cr.execute("""
            SELECT a.id, a.name, COALESCE(a.res_model, ''), a.create_uid,
                   a.file_size, a.create_date, (a.store_fname IS NOT NULL),
                   a.res_field
              FROM ir_attachment a
             WHERE """ + where + """
          ORDER BY a.file_size DESC, a.id
             LIMIT %s""", params + [limit])
        attachment_rows = cr.fetchall()

        labels = self._model_labels()
        known_users = self._existing_user_ids(
            [r[0] for r in user_rows] + [r[3] for r in attachment_rows])

        def share(size):
            return (float(size or 0) / total_size * 100.0) if total_size else 0.0

        def label_for(res_model):
            if not res_model:
                return _('Not linked to a record')
            return labels.get(res_model) or res_model

        model_vals = [(0, 0, {
            'res_model': res_model,
            'model_name': label_for(res_model),
            'attachment_count': count,
            'total_size_mb': float(size or 0) / MB,
            'size_display': format_size(size),
            'percentage': share(size),
        }) for res_model, size, count in model_rows]

        user_vals = [(0, 0, {
            'user_id': uid if uid in known_users else False,
            'attachment_count': count,
            'total_size_mb': float(size or 0) / MB,
            'size_display': format_size(size),
            'percentage': share(size),
        }) for uid, size, count in user_rows]

        attachment_vals = [(0, 0, {
            'attachment_id': att_id,
            'name': name or _('Unnamed'),
            'res_model': res_model,
            'model_name': label_for(res_model),
            'user_id': uid if uid in known_users else False,
            'file_size_mb': float(size or 0) / MB,
            'size_display': format_size(size),
            'upload_date': create_date,
            'storage': 'filestore' if on_filestore else 'db',
            'res_field': res_field or False,
            'to_delete': False,
        }) for att_id, name, res_model, uid, size, create_date, on_filestore, res_field
            in attachment_rows]

        self.write({
            'total_count': total_count,
            'total_size_mb': total_size / MB,
            'total_size_display': format_size(total_size),
            'filestore_size_display': format_size(filestore_size),
            'db_size_display': format_size(db_size),
            'model_line_ids': [(5, 0, 0)] + model_vals,
            'user_line_ids': [(5, 0, 0)] + user_vals,
            'attachment_line_ids': [(5, 0, 0)] + attachment_vals,
        })

    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Attachment Storage Report'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    @api.model
    def action_open_report(self):
        """Entry point of the menu: build a report with the default filters."""
        self._check_report_access()
        report = self.create({})
        report._compute_report()
        return report._reopen()

    def action_run_report(self):
        self.ensure_one()
        self._compute_report()
        return self._reopen()

    def action_delete_selected(self):
        """Explicit, confirmed cleanup: delete exactly the ticked attachments."""
        self.ensure_one()
        self._check_report_access()
        lines = self.attachment_line_ids.filtered(lambda line: line.to_delete)
        if not lines:
            raise UserError(_(
                'Tick the attachments you want to remove in the "Largest Attachments" '
                'tab first. Nothing is ever deleted automatically.'))
        attachments = lines.mapped('attachment_id').exists()
        if not attachments:
            raise UserError(_('The ticked attachments no longer exist.'))
        # A row with res_field set is not an upload: it *is* the value of a
        # binary field. Unlinking it silently blanks that field on the record
        # (a logo, a photo, a stored PDF) and leaves the resized siblings
        # behind, so refuse it instead of destroying data the user did not
        # realise they were ticking.
        field_lines = lines.filtered(lambda line: line.res_field)
        if field_lines:
            raise UserError(_(
                'These files are not uploads: each one is the value of a binary '
                'field on a record (a logo, a photo, a stored PDF). Deleting '
                'them would silently erase that field:\n%(rows)s\n\n'
                'Untick them, or clear the value on the record itself.'
            ) % {'rows': '\n'.join(
                '- %s (%s)' % (line.name, line.model_name) for line in field_lines)})
        freed = sum(attachments.mapped('file_size'))
        count = len(attachments)
        # drop the report rows first so the cascade never surprises the ORM
        lines.unlink()
        # no sudo(): the user's own access rights decide what may be removed
        attachments.unlink()
        self._compute_report()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Attachments deleted'),
                'message': _('%(count)s attachment(s) deleted, %(size)s freed.') % {
                    'count': count, 'size': format_size(freed)},
                'next': self._reopen(),
            },
        }


class AttachmentStorageReportModelLine(models.TransientModel):
    _name = 'attachment.storage.report.model.line'
    _description = 'Attachment Storage per Model'
    _order = 'total_size_mb desc, id'

    report_id = fields.Many2one(
        'attachment.storage.report', string='Report', required=True, ondelete='cascade', index=True)
    res_model = fields.Char(string='Technical Model', readonly=True)
    model_name = fields.Char(string='Model', readonly=True)
    attachment_count = fields.Integer(string='Attachments', readonly=True)
    total_size_mb = fields.Float(string='Size (MB)', readonly=True, digits=(16, 3))
    size_display = fields.Char(string='Size', readonly=True)
    percentage = fields.Float(string='Share', readonly=True, digits=(16, 2))

    def action_view_attachments(self):
        self.ensure_one()
        report = self.report_id
        report._check_report_access()
        action = self.env['ir.actions.act_window']._for_xml_id('base.action_attachment')
        # build a fresh list every call: _search mutates the domain on 14.0-16.0
        domain = [('file_size', '>=', int(max(report.min_size_mb or 0.0, 0.0) * MB))]
        domain.append(('res_model', '=', self.res_model) if self.res_model
                      else ('res_model', '=', False))
        action['domain'] = domain + report._attachment_domain_extra()
        action['context'] = {}
        return action


class AttachmentStorageReportUserLine(models.TransientModel):
    _name = 'attachment.storage.report.user.line'
    _description = 'Attachment Storage per User'
    _order = 'total_size_mb desc, id'

    report_id = fields.Many2one(
        'attachment.storage.report', string='Report', required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', string='Uploaded By', readonly=True, ondelete='cascade')
    attachment_count = fields.Integer(string='Attachments', readonly=True)
    total_size_mb = fields.Float(string='Size (MB)', readonly=True, digits=(16, 3))
    size_display = fields.Char(string='Size', readonly=True)
    percentage = fields.Float(string='Share', readonly=True, digits=(16, 2))

    def action_view_attachments(self):
        self.ensure_one()
        report = self.report_id
        report._check_report_access()
        action = self.env['ir.actions.act_window']._for_xml_id('base.action_attachment')
        # build a fresh list every call: _search mutates the domain on 14.0-16.0
        action['domain'] = [
            ('create_uid', '=', self.user_id.id),
            ('file_size', '>=', int(max(report.min_size_mb or 0.0, 0.0) * MB)),
        ] + report._attachment_domain_extra()
        action['context'] = {}
        return action


class AttachmentStorageReportAttachmentLine(models.TransientModel):
    _name = 'attachment.storage.report.attachment.line'
    _description = 'Largest Attachment'
    _order = 'file_size_mb desc, id'

    report_id = fields.Many2one(
        'attachment.storage.report', string='Report', required=True, ondelete='cascade', index=True)
    attachment_id = fields.Many2one(
        'ir.attachment', string='Attachment', ondelete='cascade', index=True)
    name = fields.Char(string='File Name', readonly=True)
    res_model = fields.Char(string='Technical Model', readonly=True)
    model_name = fields.Char(string='Attached To', readonly=True)
    user_id = fields.Many2one('res.users', string='Uploaded By', readonly=True, ondelete='cascade')
    file_size_mb = fields.Float(string='Size (MB)', readonly=True, digits=(16, 3))
    size_display = fields.Char(string='Size', readonly=True)
    upload_date = fields.Datetime(string='Uploaded On', readonly=True)
    storage = fields.Selection(
        [('filestore', 'Filestore'), ('db', 'Database')], string='Stored In', readonly=True)
    res_field = fields.Char(
        string='Record Field', readonly=True,
        help='Filled when this file is the value of a binary field on a record '
             '(a logo, a photo, a stored PDF) rather than an uploaded document. '
             'Those files cannot be deleted from here.')
    to_delete = fields.Boolean(
        string='Delete', default=False,
        help='Tick, then use the "Delete Ticked Attachments" button. '
             'Nothing is removed until you confirm.')

    def action_open_attachment(self):
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_('This attachment no longer exists.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Attachment'),
            'res_model': 'ir.attachment',
            'res_id': self.attachment_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }
