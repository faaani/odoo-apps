# -*- coding: utf-8 -*-
# Part of attachment_bulk_download. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import io
import logging
import re
import zipfile

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.tools import human_size

_logger = logging.getLogger(__name__)

PARAM_MAX_MB = 'attachment_bulk_download.max_total_mb'
DEFAULT_MAX_MB = 200
MB = 1024 * 1024
# Ceiling on the selection itself: the id list travels into an SQL IN () and is
# stored on the wizard, so it is bounded before the size limit can be applied.
MAX_RECORDS = 5000

# Characters that must never reach a ZIP entry name: path separators (a file
# named "../../etc/passwd" would otherwise escape its folder), the reserved
# Windows characters, and control characters.
UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
MAX_NAME_LEN = 120


class AttachmentBulkDownloadWizard(models.TransientModel):
    _name = 'attachment.bulk.download.wizard'
    _description = 'Download Attachments in Bulk'

    # Written by action_download() so the controller can rebuild the very same
    # selection server-side; the browser only ever carries this wizard's id.
    res_model = fields.Char(string='Model', readonly=True)
    res_ids = fields.Text(string='Selected Record Ids', readonly=True)

    res_model_label = fields.Char(string='Records From', readonly=True)
    record_count = fields.Integer(string='Selected Records', readonly=True)
    attachment_count = fields.Integer(string='Files to Download', readonly=True)
    total_size = fields.Char(string='Total Size', readonly=True)
    max_size = fields.Char(string='Download Limit', readonly=True)
    over_limit = fields.Boolean(string='Over the Limit', readonly=True)

    # --------------------------------------------------------------------
    # configuration
    # --------------------------------------------------------------------
    @api.model
    def _abd_max_mb(self):
        """Largest total archive size, in MB. 0 means no limit.

        Read with sudo() because it is a system-wide setting, not record data:
        every user must see the same limit, and none of them may change it.
        """
        raw = self.env['ir.config_parameter'].sudo().get_param(
            PARAM_MAX_MB, DEFAULT_MAX_MB)
        try:
            return max(int(float(raw)), 0)
        except (TypeError, ValueError, OverflowError):
            _logger.warning(
                'Ignoring invalid %s=%r, falling back to %s MB',
                PARAM_MAX_MB, raw, DEFAULT_MAX_MB)
            return DEFAULT_MAX_MB

    @api.model
    def _abd_max_bytes(self):
        return self._abd_max_mb() * MB

    # --------------------------------------------------------------------
    # selection helpers
    # --------------------------------------------------------------------
    @api.model
    def _abd_context_selection(self):
        """Return (model, ids) of the records the Action menu was opened on."""
        ctx = self.env.context
        model = ctx.get('active_model')
        ids = list(ctx.get('active_ids') or [])
        if not ids and ctx.get('active_id'):
            ids = [ctx['active_id']]
        if not model or model == self._name:
            # opened from the wizard itself, not from a record selection
            return False, []
        return model, [i for i in ids if isinstance(i, int)]

    def _abd_stored_ids(self):
        self.ensure_one()
        return [int(i) for i in (self.res_ids or '').split(',') if i.strip().isdigit()]

    @api.model
    def _abd_find_attachments(self, model, res_ids):
        """Attachments of the selection that the current user may read.

        ir.attachment.search() applies the access rules of the *linked* record,
        so attachments hanging on records the user cannot read never come back
        from this call. It also excludes attachments that back a binary field
        (res_field set), exactly like the standard Attachments list does.
        """
        if not model or not res_ids or model not in self.env:
            return self.env['ir.attachment']
        return self.env['ir.attachment'].search([
            ('res_model', '=', model),
            ('res_id', 'in', list(res_ids)),
            ('type', '=', 'binary'),
        ], order='res_id, id')

    def _abd_assert_owner(self):
        """Refuse a download request that another user prepared.

        The URL carries a wizard id, and the ACL on this transient model is the
        plain employee one, so the id alone must never be enough.
        """
        self.ensure_one()
        if self.create_uid.id != self.env.uid:
            raise AccessError(_('This download request belongs to another user.'))

    def _abd_prepare(self, model, res_ids):
        """Collect the downloadable attachments and enforce the limits."""
        if len(res_ids) > MAX_RECORDS:
            raise UserError(_(
                'A bulk download covers at most %(max)s records at a time, and '
                '%(count)s are selected. Narrow the selection and try again.'
            ) % {'max': MAX_RECORDS, 'count': len(res_ids)})
        attachments = self._abd_find_attachments(model, res_ids)
        if not attachments:
            raise UserError(_(
                'None of the %s selected record(s) has a file attached that you '
                'are allowed to download.'
            ) % len(res_ids))
        limit = self._abd_max_bytes()
        total = sum(attachments.mapped('file_size'))
        if limit and total > limit:
            raise UserError(_(
                'The selection holds %(count)s file(s) totalling %(total)s, which is '
                'more than the %(limit)s bulk download limit.\n\n'
                'Select fewer records, or ask your administrator to raise '
                '"Bulk Download Limit (MB)" in Settings > General Settings > Attachments.'
            ) % {
                'count': len(attachments),
                'total': human_size(total) or '0',
                'limit': human_size(limit) or '0',
            })
        return attachments

    # --------------------------------------------------------------------
    # naming
    # --------------------------------------------------------------------
    @api.model
    def _abd_safe_name(self, name, fallback):
        """Turn a record or file name into one safe ZIP path segment."""
        cleaned = UNSAFE_CHARS.sub('_', (name or '').strip())
        # leading/trailing dots and spaces would give ".." segments or names
        # Windows refuses to extract
        cleaned = cleaned.strip('. ')
        return (cleaned or fallback)[:MAX_NAME_LEN]

    @api.model
    def _abd_unique_entry(self, folder, filename, used):
        """Build "<folder>/<filename>", numbering same-name files in a folder.

        Files with the same name on *different* records already differ by their
        folder, so both are kept. Two identically named files on the *same*
        record become "report.pdf" and "report (2).pdf".
        """
        stem, dot, suffix = filename.rpartition('.')
        ext = '.' + suffix if dot else ''
        if not dot:
            stem = filename
        candidate = '%s/%s' % (folder, filename)
        counter = 1
        while candidate.lower() in used:
            counter += 1
            candidate = '%s/%s (%s)%s' % (folder, stem, counter, ext)
        used.add(candidate.lower())
        return candidate

    @api.model
    def _abd_record_names(self, model, res_ids):
        """{id: display name} for the records that own the attachments."""
        names = {}
        ordered = list(dict.fromkeys(res_ids))
        # read-only: these raise before any write, so there is nothing for a
        # savepoint to roll back and a plain try/except is enough
        try:
            for record in self.env[model].browse(ordered):
                names[record.id] = record.display_name
        except (AccessError, MissingError):
            # one unreadable record must not cost us every name: retry one by one
            names = {}
            for res_id in ordered:
                try:
                    names[res_id] = self.env[model].browse(res_id).display_name
                except (AccessError, MissingError):
                    names[res_id] = False
        return names

    def _abd_zip_filename(self, names):
        self.ensure_one()
        if len(names) == 1:
            only = list(names.values())[0]
            return '%s.zip' % self._abd_safe_name(only, 'attachments')
        return 'attachments-%s-records.zip' % len(names)

    @api.model
    def _abd_forget(self, attachment):
        """Drop a file's content from the ORM cache once it is in the archive."""
        fnames = ['raw', 'datas', 'db_datas']
        try:
            attachment.invalidate_recordset(fnames)
        except AttributeError:  # Odoo 15.0 and older
            attachment.invalidate_cache(fnames, attachment.ids)

    # --------------------------------------------------------------------
    # wizard
    # --------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super(AttachmentBulkDownloadWizard, self).default_get(fields_list)
        model, res_ids = self._abd_context_selection()
        # too many records to even count cheaply: say so instead of searching
        too_many = len(res_ids) > MAX_RECORDS
        attachments = self.env['ir.attachment'] if too_many \
            else self._abd_find_attachments(model, res_ids)
        total = sum(attachments.mapped('file_size'))
        limit = self._abd_max_bytes()
        label = model or ''
        if model and model in self.env:
            label = self.env['ir.model']._get(model).name or model
        res.update(
            res_model=model or False,
            res_ids=','.join(str(i) for i in res_ids),
            res_model_label=label,
            record_count=len(res_ids),
            attachment_count=len(attachments),
            total_size=human_size(total) or '0',
            max_size=human_size(limit) if limit else _('no limit'),
            over_limit=too_many or (bool(limit) and total > limit),
        )
        return res

    def action_download(self):
        """Validate the selection, remember it, and send the browser to the ZIP."""
        self.ensure_one()
        model, res_ids = self._abd_context_selection()
        if not model:
            model, res_ids = self.res_model, self._abd_stored_ids()
        if not model or not res_ids:
            raise UserError(_(
                'Select the records whose attachments you want to download first.'))
        # raises UserError when there is nothing to download or the archive
        # would be over the limit, before anything is built
        self._abd_prepare(model, res_ids)
        self.write({
            'res_model': model,
            'res_ids': ','.join(str(i) for i in res_ids),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/attachment_bulk_download/%s' % self.id,
            # 'new': the download response closes the tab by itself, and if the
            # archive is refused the user keeps the list view they came from
            'target': 'new',
        }

    def _abd_build_zip(self):
        """Return (filename, zip bytes) for this wizard's stored selection.

        Called by the controller: the attachments are looked up again here, as
        the logged-in user, so what the browser asks for can never widen what
        the archive contains.
        """
        self.ensure_one()
        model = self.res_model
        res_ids = self._abd_stored_ids()
        if not model or not res_ids:
            raise UserError(_('This download request no longer holds any record.'))
        attachments = self._abd_prepare(model, res_ids)
        names = self._abd_record_names(model, attachments.mapped('res_id'))

        limit = self._abd_max_bytes()
        buffer = io.BytesIO()
        used = set()
        written = 0
        skipped = 0
        read_bytes = 0
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for attachment in attachments:
                try:
                    # read-only: an unreadable attachment raises before any
                    # write, so a plain try/except isolates it just as well as
                    # a savepoint would, without flushing the environment
                    content = attachment.raw or b''
                except (AccessError, MissingError):
                    continue
                if not content and attachment.file_size:
                    # the row says there is a file but the filestore has none:
                    # skip it rather than hand the user an empty document
                    _logger.warning(
                        'Bulk download: attachment %s has no readable file, skipped',
                        attachment.id)
                    skipped += 1
                    continue
                read_bytes += len(content)
                if limit and read_bytes > limit:
                    # file_size is only a stored column; this is the real bound
                    raise UserError(_(
                        'The files are larger than the %s bulk download limit. '
                        'Select fewer records, or ask your administrator to raise '
                        '"Bulk Download Limit (MB)" in Settings.'
                    ) % (human_size(limit) or '0'))
                folder = self._abd_safe_name(
                    names.get(attachment.res_id) or '',
                    '%s-%s' % (model.replace('.', '-'), attachment.res_id))
                entry = self._abd_unique_entry(
                    folder, self._abd_safe_name(attachment.name, 'unnamed-file'), used)
                archive.writestr(entry, content)
                written += 1
                self._abd_forget(attachment)
        if not written:
            raise UserError(_(
                'None of the selected files could be read, so there is nothing to '
                'download.'))
        if skipped:
            _logger.warning(
                'Bulk download: %s of %s files were missing from the filestore '
                'and are not in the archive', skipped, len(attachments))
        return self._abd_zip_filename(names), buffer.getvalue()
