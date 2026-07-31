# -*- coding: utf-8 -*-
# Part of attachment_link_checker. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import hashlib
import logging
import os
from stat import S_ISREG

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Files are hashed 512 KB at a time: a 2 GB attachment must never be read into
# memory in one piece just to verify its checksum.
CHUNK_SIZE = 512 * 1024

MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 5000
DEFAULT_BATCH_SIZE = 500

DEFAULT_RESULT_LINES = 500
MAX_RESULT_LINES = 5000

# One row per model: tiny even on a badly damaged database.
MODEL_LINE_LIMIT = 500

# The filestore de-duplicates identical contents, so one file can back many
# attachments. Remembering what each path looked like saves a stat() - and, with
# checksums on, a full re-read - but the cache itself must stay bounded.
STAT_CACHE_MAX = 50000

PROBLEM_MISSING = 'missing'
PROBLEM_NOT_A_FILE = 'not_a_file'
PROBLEM_UNREADABLE = 'unreadable'
PROBLEM_SIZE = 'size'
PROBLEM_CHECKSUM = 'checksum'

# Only a row whose file is truly gone may be removed by the optional cleanup.
# A size or checksum mismatch means the file is still there, and it is the only
# copy left - deleting the record would destroy it.
DELETABLE_PROBLEMS = (PROBLEM_MISSING,)


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


class AttachmentLinkCheck(models.TransientModel):
    _name = 'attachment.link.check'
    _description = 'Attachment File Check'

    # keeps the breadcrumb readable instead of "attachment.link.check,4"
    name = fields.Char(
        string='Check', readonly=True,
        default=lambda self: _('Attachment File Check'))

    # ------------------------------------------------------------------
    # what to look at
    # ------------------------------------------------------------------
    res_model_id = fields.Many2one(
        'ir.model', string='Limit to Model', ondelete='cascade',
        help='Check only the attachments linked to this model. '
             'Leave empty to check every attachment.')
    date_from = fields.Datetime(
        string='Uploaded From', help='Only check attachments created on or after this moment.')
    date_to = fields.Datetime(
        string='Uploaded Until', help='Only check attachments created on or before this moment.')
    include_field_attachments = fields.Boolean(
        string='Include Field Attachments', default=True,
        help='Binary field values (company logos, product images, stored report '
             'PDFs) are attachments too, and their file can go missing just like '
             'an uploaded document. Untick to check user uploads only.')

    # ------------------------------------------------------------------
    # how deep to look
    # ------------------------------------------------------------------
    check_size = fields.Boolean(
        string='Compare File Sizes', default=True,
        help='Also report files whose size on disk differs from the size recorded '
             'in the database. Costs one extra stat() per file, no reading.')
    check_checksum = fields.Boolean(
        string='Verify Checksums', default=False,
        help='Also recompute the SHA1 of every file and compare it with the one '
             'stored on the attachment. This catches a corrupted file whose size '
             'did not change, but it reads every byte of the filestore. On a large '
             'filestore combine it with "Stop After" so the scan cannot outlast '
             'the server request timeout and lose its result.')
    batch_size = fields.Integer(
        string='Batch Size', default=DEFAULT_BATCH_SIZE,
        help='How many attachments are processed at a time (1-5000; values outside '
             'that range are clamped). The attachment table is read page by page, '
             'never in one go.')
    max_scan = fields.Integer(
        string='Stop After', default=0,
        help='Stop the scan after this many attachments. 0 checks all of them.')
    max_results = fields.Integer(
        string='Broken Rows to List', default=DEFAULT_RESULT_LINES,
        help='How many broken attachments to list in detail (1-5000; values outside '
             'that range are clamped). The counts above always cover the whole scan, '
             'even when the list is truncated.')

    # ------------------------------------------------------------------
    # results
    # ------------------------------------------------------------------
    scan_date = fields.Datetime(string='Checked On', readonly=True)
    storage_backend = fields.Char(string='Storage Backend', readonly=True)
    filestore_path = fields.Char(string='Filestore Directory', readonly=True)

    scanned_count = fields.Integer(string='Attachments Examined', readonly=True)
    hidden_count = fields.Integer(
        string='Hidden From You', readonly=True,
        help='Attachments that matched the filters but were not examined because '
             'Odoo hides attachments whose linked record belongs to a model your '
             'user may not read. Run the scan as a user with access to every app '
             'to bring this to zero.')
    filestore_count = fields.Integer(string='Checked on Disk', readonly=True)
    database_count = fields.Integer(string='Stored in Database', readonly=True)
    url_count = fields.Integer(string='Link (URL) Attachments', readonly=True)
    no_content_count = fields.Integer(string='Without Any Content', readonly=True)

    ok_count = fields.Integer(string='Files Found', readonly=True)
    broken_count = fields.Integer(string='Broken', readonly=True)
    missing_count = fields.Integer(string='File Missing', readonly=True)
    size_mismatch_count = fields.Integer(string='Wrong Size', readonly=True)
    checksum_mismatch_count = fields.Integer(string='Wrong Checksum', readonly=True)
    unreadable_count = fields.Integer(string='Unreadable', readonly=True)
    no_checksum_count = fields.Integer(string='No Stored Checksum', readonly=True)
    lost_size_display = fields.Char(string='Lost Content', readonly=True)

    batch_count = fields.Integer(
        string='Pages Read', readonly=True,
        help='How many pages the scan read from the database. The table is walked '
             'a page at a time instead of being loaded in one go.')
    truncated = fields.Boolean(string='List Truncated', readonly=True)
    stopped_early = fields.Boolean(string='Stopped Early', readonly=True)
    scan_note = fields.Text(string='Result', readonly=True)

    line_ids = fields.One2many(
        'attachment.link.check.line', 'check_id', string='Broken Attachments')
    model_line_ids = fields.One2many(
        'attachment.link.check.model.line', 'check_id', string='By Model')

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _check_scan_access(self):
        """The scan walks every attachment row and exposes filestore paths, so
        it is reserved to Settings administrators."""
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_(
                'Only Settings administrators may check attachment files.'))

    def _flush_attachments(self):
        """Make sure pending ORM writes hit the database before we read it."""
        attachment = self.env['ir.attachment']
        flush_model = getattr(attachment, 'flush_model', None)
        if flush_model:  # 16.0+
            flush_model()
        else:  # 14.0 - 15.0
            attachment.flush()

    def _forget(self, records):
        """Drop a processed batch from the ORM cache so a long scan keeps a
        constant memory footprint."""
        invalidate = getattr(records, 'invalidate_recordset', None)
        if invalidate:  # 16.0+
            invalidate()
        else:  # 14.0 - 15.0 (invalidates the whole cache, which is why the scan
               # loop keeps its own parameters in local variables)
            records.invalidate_cache()

    def _static_scan_domain(self):
        """Everything the user asked to look at, minus the paging clause.

        Built once per scan: on 14.0/15.0 dropping a batch from the cache clears
        the whole environment cache, so rebuilding this per page would re-read
        the wizard row every time.
        """
        self.ensure_one()
        domain = [
            '|', ('company_id', '=', False),
            ('company_id', 'in', list(self.env.companies.ids) or [0]),
        ]
        if not self.include_field_attachments:
            domain.append(('res_field', '=', False))
        if self.res_model_id:
            domain.append(('res_model', '=', self.res_model_id.model))
        if self.date_from:
            domain.append(('create_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('create_date', '<=', self.date_to))
        return domain

    @staticmethod
    def _page_domain(static_domain, last_id):
        """One page of attachments, taken after ``last_id``.

        Paging is done on the id rather than on an offset: ir.attachment filters
        the result of its own ``_search`` against the access rules of the linked
        records, so a page can come back shorter than the limit and offsets would
        silently skip rows. Naming ``id`` also disables the implicit
        ``res_field = False`` filter that ir.attachment adds to every search,
        which is what we want - binary field values are attachments whose file
        can go missing too.
        """
        return list(static_domain) + [('id', '>', last_id)]

    def _coverage_total(self, static_domain):
        """How many attachments match the filters in total, hidden ones included.

        ir.attachment removes from every non-superuser search the attachments
        whose linked record belongs to a model the user has no access to. A
        Settings administrator who does not also hold the Accounting or HR
        groups therefore never sees those rows, and a scan could report a clean
        bill of health on a filestore that has lost every invoice PDF.

        sudo() here runs a COUNT and nothing else: no attachment row, no field
        and no file content is ever read through it. It exists so the report can
        say how much it was not allowed to look at, instead of quietly leaving
        it out.
        """
        self.ensure_one()
        return self.env['ir.attachment'].sudo().search_count(
            self._page_domain(static_domain, 0))

    def _ids_stored_in_database(self, attachment_ids):
        """Ids of the given attachments whose content sits in the database.

        Only the ids are selected: reading ``db_datas`` here would pull every
        blob of the batch into memory, which is precisely what this module
        promises never to do.
        """
        if not attachment_ids:
            return set()
        self.env.cr.execute(
            'SELECT id FROM ir_attachment WHERE id IN %s AND db_datas IS NOT NULL',
            (tuple(attachment_ids),))
        return {row[0] for row in self.env.cr.fetchall()}

    def _resolve_path(self, attachment, store_fname):
        """The attachment's own path helper, in a savepoint.

        A third-party storage backend may override ``_full_path`` with something
        that queries the database; if that raises, the transaction would be left
        aborted and every later statement of the scan would fail far from the
        cause.
        """
        with self.env.cr.savepoint():
            return attachment._full_path(store_fname)

    @staticmethod
    def _stat_file(full_path):
        """Look at one filestore path without reading it."""
        try:
            info = os.stat(full_path)
        except FileNotFoundError:
            return {'state': PROBLEM_MISSING, 'size': 0, 'detail': '', 'sha1': None}
        except OSError as exc:
            return {'state': PROBLEM_UNREADABLE, 'size': 0,
                    'detail': exc.strerror or str(exc), 'sha1': None}
        if not S_ISREG(info.st_mode):
            return {'state': PROBLEM_NOT_A_FILE, 'size': 0,
                    'detail': _('the path exists but is not a regular file'),
                    'sha1': None}
        return {'state': 'ok', 'size': info.st_size, 'detail': '', 'sha1': None}

    @staticmethod
    def _file_sha1(full_path):
        """SHA1 of a file, read in chunks - the same digest Odoo stores in
        ir_attachment.checksum."""
        digest = hashlib.sha1()
        with open(full_path, 'rb') as handle:
            while True:
                block = handle.read(CHUNK_SIZE)
                if not block:
                    break
                digest.update(block)
        return digest.hexdigest()

    def _resolve_record_names(self, wanted):
        """Best effort display name for the records the broken files belong to.

        ``wanted`` is ``{res_model: set(res_id)}`` and is bounded by the number
        of listed rows. A model that no longer exists in the registry - the
        normal case on a half-finished migration - or one the user may not read
        simply yields no name instead of breaking the whole report.
        """
        names = {}
        for model_name, res_ids in wanted.items():
            if not model_name or model_name not in self.env:
                continue
            try:
                with self.env.cr.savepoint():
                    records = self.env[model_name].browse(sorted(res_ids)).exists()
                    for record in records:
                        names[(model_name, record.id)] = record.display_name
            except Exception:  # noqa: BLE001 - a broken model must not abort the report
                _logger.info('attachment_link_checker: cannot read names of %s',
                             model_name, exc_info=True)
        return names

    def _model_labels(self):
        """Technical model name -> translated label, for the report only.

        No sudo(): base.group_system implies base.group_erp_manager, which has
        read access to ir.model on every supported series. Only the two columns
        that are displayed are read.
        """
        return {row['model']: row['name']
                for row in self.env['ir.model'].search_read([], ['model', 'name'])}

    # ------------------------------------------------------------------
    # the scan
    # ------------------------------------------------------------------
    def _run_check(self):
        """Walk the attachment table in batches and collect the broken files.

        Nothing is written to ir.attachment and nothing is deleted: this is a
        report.
        """
        self.ensure_one()
        self._check_scan_access()
        self._flush_attachments()

        Attachment = self.env['ir.attachment']
        batch_size = min(max(self.batch_size or DEFAULT_BATCH_SIZE, MIN_BATCH_SIZE),
                         MAX_BATCH_SIZE)
        max_lines = min(max(self.max_results or DEFAULT_RESULT_LINES, 1), MAX_RESULT_LINES)
        max_scan = max(self.max_scan or 0, 0)
        static_domain = self._static_scan_domain()
        # read once: dropping a batch from the cache also drops this record's
        # own fields on 14.0/15.0, and re-reading them per attachment would add
        # a query for nothing
        check_size = self.check_size
        check_checksum = self.check_checksum

        counters = {
            'scanned': 0, 'filestore': 0, 'database': 0, 'url': 0, 'no_content': 0,
            'ok': 0, 'broken': 0, 'no_checksum': 0,
        }
        problems = {
            PROBLEM_MISSING: 0, PROBLEM_NOT_A_FILE: 0, PROBLEM_UNREADABLE: 0,
            PROBLEM_SIZE: 0, PROBLEM_CHECKSUM: 0,
        }
        per_model = {}
        broken_rows = []
        wanted_names = {}
        # one stat() per distinct file, shared across pages but capped
        path_cache = {}
        lost_bytes = 0
        batch_count = 0
        last_id = 0
        stopped_early = False

        while True:
            limit = batch_size
            if max_scan:
                remaining = max_scan - counters['scanned']
                if remaining <= 0:
                    # only claim we stopped early if something was really left
                    stopped_early = bool(Attachment.search(
                        self._page_domain(static_domain, last_id), limit=1))
                    break
                limit = min(batch_size, remaining)

            batch = Attachment.search(
                self._page_domain(static_domain, last_id), limit=limit, order='id')
            if not batch:
                break
            batch_count += 1
            last_id = max(batch.ids)
            in_database = self._ids_stored_in_database(batch.ids)

            for attachment in batch:
                counters['scanned'] += 1
                store_fname = attachment.store_fname
                if not store_fname:
                    if attachment.id in in_database:
                        counters['database'] += 1
                    elif attachment.type == 'url':
                        counters['url'] += 1
                    else:
                        counters['no_content'] += 1
                    continue

                counters['filestore'] += 1
                problem, detail, full_path = self._check_one(
                    attachment, store_fname, path_cache, counters,
                    check_size, check_checksum)
                if not problem:
                    counters['ok'] += 1
                    continue

                counters['broken'] += 1
                problems[problem] += 1
                lost_bytes += attachment.file_size or 0
                res_model = attachment.res_model or ''
                figures = per_model.setdefault(res_model, {'count': 0, 'size': 0})
                figures['count'] += 1
                figures['size'] += attachment.file_size or 0
                if len(broken_rows) < max_lines:
                    broken_rows.append({
                        'attachment_id': attachment.id,
                        'name': attachment.name or _('Unnamed'),
                        'res_model': res_model,
                        'res_id': attachment.res_id or 0,
                        'user_id': attachment.create_uid.id,
                        'upload_date': attachment.create_date,
                        'file_size': attachment.file_size or 0,
                        'size_display': format_size(attachment.file_size),
                        'store_fname': store_fname,
                        'full_path': full_path,
                        'res_field': attachment.res_field or False,
                        'problem': problem,
                        'problem_detail': detail,
                        'to_delete': False,
                    })
                    if res_model and attachment.res_id:
                        wanted_names.setdefault(res_model, set()).add(attachment.res_id)

            # a short page does not mean the end: ir.attachment filters its own
            # search result against the access rules of the linked records, so
            # the loop stops on an empty page only
            self._forget(batch)

        # how much of the table the current user was not allowed to see; with a
        # "Stop After" cap the difference would be the rows we skipped on
        # purpose, so the question is only meaningful for a complete pass
        hidden = 0
        if not stopped_early:
            hidden = max(self._coverage_total(static_domain) - counters['scanned'], 0)

        self._store_results(counters, problems, per_model, broken_rows, wanted_names,
                            lost_bytes, batch_count, hidden, stopped_early)

    def _check_one(self, attachment, store_fname, path_cache, counters,
                   check_size, check_checksum):
        """Verify one filestore-backed attachment. Returns (problem, detail, path)."""
        try:
            # the attachment resolves its own path: honours a custom filestore
            # location and stays correct across series
            full_path = self._resolve_path(attachment, store_fname)
        except Exception as exc:  # noqa: BLE001 - one bad row must not abort the scan
            _logger.info('attachment_link_checker: cannot resolve path of attachment %s',
                         attachment.id, exc_info=True)
            return PROBLEM_UNREADABLE, str(exc), store_fname

        info = path_cache.get(store_fname)
        if info is None:
            info = self._stat_file(full_path)
            if len(path_cache) < STAT_CACHE_MAX:
                path_cache[store_fname] = info

        if info['state'] != 'ok':
            return info['state'], info['detail'], full_path

        expected_size = attachment.file_size or 0
        if check_size and expected_size and info['size'] != expected_size:
            return PROBLEM_SIZE, _(
                'the database records %(expected)s, the file on disk is %(found)s'
            ) % {'expected': format_size(expected_size),
                 'found': format_size(info['size'])}, full_path

        if check_checksum:
            expected = (attachment.checksum or '').strip().lower()
            if not expected:
                counters['no_checksum'] += 1
            else:
                if info['sha1'] is None:
                    try:
                        info['sha1'] = self._file_sha1(full_path)
                    except OSError as exc:
                        info['sha1'] = False
                        info['detail'] = exc.strerror or str(exc)
                if info['sha1'] is False:
                    return PROBLEM_UNREADABLE, info['detail'], full_path
                if info['sha1'] != expected:
                    return PROBLEM_CHECKSUM, _(
                        'the database records %(expected)s, the file on disk hashes '
                        'to %(found)s'
                    ) % {'expected': expected, 'found': info['sha1']}, full_path

        return None, '', full_path

    def _store_results(self, counters, problems, per_model, broken_rows, wanted_names,
                       lost_bytes, batch_count, hidden, stopped_early):
        """Turn the collected numbers into the report the user reads."""
        self.ensure_one()
        labels = self._model_labels() if per_model else {}
        names = self._resolve_record_names(wanted_names)

        def label_for(res_model):
            if not res_model:
                return _('Not linked to a record')
            return labels.get(res_model) or res_model

        line_vals = []
        for row in broken_rows:
            row = dict(row)
            row['model_name'] = label_for(row['res_model'])
            row['record_name'] = names.get((row['res_model'], row['res_id']), '')
            line_vals.append((0, 0, row))

        model_vals = []
        ranked = sorted(per_model.items(), key=lambda item: (-item[1]['count'], item[0]))
        for res_model, figures in ranked[:MODEL_LINE_LIMIT]:
            model_vals.append((0, 0, {
                'res_model': res_model,
                'model_name': label_for(res_model),
                'broken_count': figures['count'],
                'lost_size': float(figures['size'] or 0),
                'size_display': format_size(figures['size']),
            }))

        truncated = len(broken_rows) < counters['broken']
        notes = []
        if not counters['scanned']:
            notes.append(_('No attachment matched the filters.'))
        elif not counters['broken']:
            notes.append(_(
                'All %(files)s file(s) on disk were found. Nothing is broken.'
            ) % {'files': counters['filestore']})
        else:
            notes.append(_(
                '%(broken)s of %(files)s file(s) on disk could not be verified.'
            ) % {'broken': counters['broken'], 'files': counters['filestore']})
        if hidden:
            notes.append(_(
                '%(hidden)s attachment(s) matched the filters but were NOT examined: '
                'Odoo hides attachments whose linked record belongs to a model your '
                'user may not read. Run the scan as a user with access to every app '
                'to cover them.'
            ) % {'hidden': hidden})
        if truncated:
            notes.append(_(
                'Only the first %(shown)s broken attachment(s) are listed below; the '
                'counts cover all %(total)s. Raise "Broken Rows to List" to see more.'
            ) % {'shown': len(broken_rows), 'total': counters['broken']})
        if len(ranked) > MODEL_LINE_LIMIT:
            notes.append(_(
                'Only the %(shown)s models with the most broken files are summarised '
                'in the "By Model" tab, out of %(total)s.'
            ) % {'shown': MODEL_LINE_LIMIT, 'total': len(ranked)})
        if stopped_early:
            notes.append(_(
                'The scan stopped after %(scanned)s attachment(s) because of the '
                '"Stop After" limit, so more attachments remain unchecked.'
            ) % {'scanned': counters['scanned']})
        if counters['database'] or counters['url'] or counters['no_content']:
            notes.append(_(
                '%(db)s attachment(s) stored inside the database, %(url)s link (URL) '
                'attachment(s) and %(empty)s attachment(s) with no content at all hold '
                'no file on disk and were excluded from the disk check.'
            ) % {'db': counters['database'], 'url': counters['url'],
                 'empty': counters['no_content']})
        if self.check_checksum and counters['no_checksum']:
            notes.append(_(
                '%(count)s file(s) have no checksum stored in the database, so their '
                'content could not be verified.'
            ) % {'count': counters['no_checksum']})
        elif not self.check_checksum:
            notes.append(_(
                'Checksums were not verified. Tick "Verify Checksums" to also detect '
                'a corrupted file whose size did not change.'))
        notes.append(_(
            'Nothing was deleted: this scan only reports. Restoring the filestore may '
            'bring the missing files back.'))

        self.write({
            'scan_date': fields.Datetime.now(),
            'storage_backend': self.env['ir.attachment']._storage(),
            'filestore_path': self.env['ir.attachment']._filestore(),
            'scanned_count': counters['scanned'],
            'hidden_count': hidden,
            'filestore_count': counters['filestore'],
            'database_count': counters['database'],
            'url_count': counters['url'],
            'no_content_count': counters['no_content'],
            'ok_count': counters['ok'],
            'broken_count': counters['broken'],
            'missing_count': problems[PROBLEM_MISSING],
            'size_mismatch_count': problems[PROBLEM_SIZE],
            'checksum_mismatch_count': problems[PROBLEM_CHECKSUM],
            'unreadable_count': problems[PROBLEM_UNREADABLE] + problems[PROBLEM_NOT_A_FILE],
            'no_checksum_count': counters['no_checksum'],
            'lost_size_display': format_size(lost_bytes),
            'batch_count': batch_count,
            'truncated': truncated,
            'stopped_early': stopped_early,
            'scan_note': '\n'.join(notes),
            'line_ids': [(5, 0, 0)] + line_vals,
            'model_line_ids': [(5, 0, 0)] + model_vals,
        })

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Check Attachment Files'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    @api.model
    def action_open_check(self):
        """Entry point of the menu: run a scan with the default options."""
        self._check_scan_access()
        check = self.create({})
        check._run_check()
        return check._reopen()

    def action_run_check(self):
        self.ensure_one()
        self._run_check()
        return self._reopen()

    def action_delete_ticked(self):
        """Optional cleanup: drop the ticked dangling attachment records.

        Every ticked row is checked against the disk again first, so a file that
        came back with a restore can never be deleted by a stale report.
        """
        self.ensure_one()
        self._check_scan_access()
        lines = self.line_ids.filtered(lambda line: line.to_delete)
        if not lines:
            raise UserError(_(
                'Tick the rows you want to remove first. This scan never deletes '
                'anything on its own.'))

        kept = lines.filtered(lambda line: line.problem not in DELETABLE_PROBLEMS)
        if kept:
            raise UserError(_(
                'Only rows whose file is missing may be removed. These files are '
                'still on disk and this attachment is the only record pointing at '
                'them:\n%(rows)s'
            ) % {'rows': '\n'.join('- %s (%s)' % (line.name, line.problem_label)
                                   for line in kept[:20])})

        field_lines = lines.filtered(lambda line: line.res_field)
        if field_lines:
            raise UserError(_(
                'These rows are not uploads: each one is the value of a binary field '
                'on a record (a logo, a photo, a stored report). Clear the field on '
                'the record itself instead:\n%(rows)s'
            ) % {'rows': '\n'.join('- %s (%s)' % (line.name, line.model_name)
                                   for line in field_lines[:20])})

        # look at the disk again before touching anything: a restore may have
        # brought the files back since the report was produced
        recovered = self.env['attachment.link.check.line']
        unresolved = self.env['attachment.link.check.line']
        targets = []
        for line in lines:
            attachment = line.attachment_id.exists()
            if not attachment:
                continue
            store_fname = attachment.store_fname
            if not store_fname:
                # the content is no longer on disk at all: it came back inside
                # the database, so this record is not dangling any more
                recovered |= line
                continue
            try:
                info = self._stat_file(self._resolve_path(attachment, store_fname))
            except Exception:  # noqa: BLE001 - fail closed, never delete on a doubt
                _logger.info('attachment_link_checker: cannot re-check attachment %s',
                             attachment.id, exc_info=True)
                unresolved |= line
                continue
            if info['state'] != PROBLEM_MISSING:
                recovered |= line
                continue
            targets.append((line, attachment))

        if recovered:
            raise UserError(_(
                'The content of these attachments is back, so nothing was deleted. '
                'Run the check again:\n%(rows)s'
            ) % {'rows': '\n'.join('- %s' % line.name for line in recovered[:20])})
        if unresolved:
            raise UserError(_(
                'The file of these attachments could not be located a second time, so '
                'nothing was deleted. A storage backend may be unavailable:\n%(rows)s'
            ) % {'rows': '\n'.join('- %s' % line.name for line in unresolved[:20])})

        deleted, refused = 0, []
        for line, attachment in targets:
            # one failure must not abort the whole cleanup
            try:
                with self.env.cr.savepoint():
                    # no sudo(): the user's own access rights decide what may go
                    attachment.unlink()
                deleted += 1
            except Exception as exc:  # noqa: BLE001
                _logger.info('attachment_link_checker: cannot delete attachment %s',
                             attachment.id, exc_info=True)
                refused.append('%s (%s)' % (line.name, exc))

        self._run_check()
        message = _('%(count)s dangling attachment record(s) deleted. No file was '
                    'removed from the filestore - there was none left to remove.'
                    ) % {'count': deleted}
        if refused:
            # the notification collapses newlines, so keep it on one line
            message += _(' %(count)s could not be deleted: %(rows)s') % {
                'count': len(refused), 'rows': ' · '.join(refused[:10])}
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning' if refused else 'success',
                'title': _('Cleanup done'),
                'message': message,
                'next': self._reopen(),
            },
        }


class AttachmentLinkCheckLine(models.TransientModel):
    _name = 'attachment.link.check.line'
    _description = 'Broken Attachment File'
    _order = 'model_name, record_name, id'

    check_id = fields.Many2one(
        'attachment.link.check', string='Check', required=True,
        ondelete='cascade', index=True)
    attachment_id = fields.Many2one(
        'ir.attachment', string='Attachment', ondelete='cascade', index=True)
    name = fields.Char(string='File Name', readonly=True)
    res_model = fields.Char(string='Technical Model', readonly=True)
    model_name = fields.Char(string='Model', readonly=True)
    res_id = fields.Integer(string='Record ID', readonly=True)
    record_name = fields.Char(
        string='Record', readonly=True,
        help='Empty when the record was deleted, or when its model no longer '
             'exists in this database.')
    user_id = fields.Many2one(
        'res.users', string='Uploaded By', readonly=True, ondelete='cascade')
    upload_date = fields.Datetime(string='Uploaded On', readonly=True)
    file_size = fields.Integer(string='Size (bytes)', readonly=True)
    size_display = fields.Char(string='Size', readonly=True)
    store_fname = fields.Char(string='Filestore Key', readonly=True)
    full_path = fields.Char(string='Expected Path', readonly=True)
    res_field = fields.Char(
        string='Record Field', readonly=True,
        help='Filled when this file is the value of a binary field on a record '
             '(a logo, a photo, a stored report) rather than an uploaded document.')
    problem = fields.Selection(
        [(PROBLEM_MISSING, 'File missing'),
         (PROBLEM_NOT_A_FILE, 'Not a regular file'),
         (PROBLEM_UNREADABLE, 'Unreadable'),
         (PROBLEM_SIZE, 'Size differs'),
         (PROBLEM_CHECKSUM, 'Checksum differs')],
        string='Problem', readonly=True)
    problem_detail = fields.Char(string='Details', readonly=True)
    to_delete = fields.Boolean(
        string='Delete', default=False,
        help='Tick, then use "Delete Ticked Records". Only rows whose file is '
             'missing can be removed, and nothing happens until you confirm.')

    @property
    def problem_label(self):
        """The translated label of this row's problem, for error messages."""
        self.ensure_one()
        labels = dict(self._fields['problem']._description_selection(self.env))
        return labels.get(self.problem, self.problem or '')

    def action_open_attachment(self):
        self.ensure_one()
        if not self.attachment_id.exists():
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

    def action_open_record(self):
        self.ensure_one()
        if not self.res_model or not self.res_id:
            raise UserError(_('This attachment is not linked to any record.'))
        if self.res_model not in self.env:
            raise UserError(_(
                'The model "%(model)s" does not exist in this database any more.'
            ) % {'model': self.res_model})
        record = self.env[self.res_model].browse(self.res_id).exists()
        if not record:
            raise UserError(_(
                'The record this file belonged to (%(model)s, id %(res_id)s) has '
                'already been deleted.'
            ) % {'model': self.model_name or self.res_model, 'res_id': self.res_id})
        return {
            'type': 'ir.actions.act_window',
            'name': self.record_name or self.model_name,
            'res_model': self.res_model,
            'res_id': record.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }


class AttachmentLinkCheckModelLine(models.TransientModel):
    _name = 'attachment.link.check.model.line'
    _description = 'Broken Attachment Files per Model'
    _order = 'broken_count desc, model_name, id'

    check_id = fields.Many2one(
        'attachment.link.check', string='Check', required=True,
        ondelete='cascade', index=True)
    res_model = fields.Char(string='Technical Model', readonly=True)
    model_name = fields.Char(string='Model', readonly=True)
    broken_count = fields.Integer(string='Broken Attachments', readonly=True)
    lost_size = fields.Float(string='Lost (bytes)', readonly=True)
    size_display = fields.Char(string='Lost Content', readonly=True)
