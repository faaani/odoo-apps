# -*- coding: utf-8 -*-
# Part of duplicate_attachment_cleaner. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, MissingError, UserError

# Attachments of these framework models are never reported and never deleted:
# they are the asset bundles, the report/module plumbing kept by Odoo itself.
EXCLUDED_MODELS = ('ir.ui.view', 'ir.asset', 'ir.actions.report', 'ir.module.module')

# At most this many groups are listed, whatever the user asks for, so that the
# read-back below always stays bounded.
MAX_LISTED_GROUPS = 1000
# Attachments are deleted in slices of this size.
UNLINK_BATCH = 200

# Aggregate over the checksum column; the attachment table itself is never
# browsed. Only the groups that end up on screen are read back.
# %s parameters, in order: excluded models, minimum file size.
WHERE_SQL = """
     WHERE checksum IS NOT NULL
       AND checksum != ''
       AND (res_field IS NULL OR res_field = '')
       AND (res_model IS NULL OR res_model NOT IN %s)
       AND COALESCE(file_size, 0) > 0
       AND COALESCE(file_size, 0) >= %s
"""
# 'record' scope: identical bytes attached to the SAME record. Deleting the
# extra copies can never leave a record without the file.
GROUPED_SQL_RECORD = """
    SELECT checksum,
           COALESCE(res_model, '') AS res_model,
           COALESCE(res_id, 0) AS res_id,
           COUNT(*) AS copies,
           MIN(COALESCE(file_size, 0)) AS size
      FROM ir_attachment
""" + WHERE_SQL + """
  GROUP BY checksum, COALESCE(res_model, ''), COALESCE(res_id, 0)
    HAVING COUNT(*) > 1
"""
# 'global' scope: identical bytes anywhere. One copy survives for the whole
# database, so records that had their own copy keep no link to the file.
GROUPED_SQL_GLOBAL = """
    SELECT checksum,
           '' AS res_model,
           0 AS res_id,
           COUNT(*) AS copies,
           MIN(COALESCE(file_size, 0)) AS size
      FROM ir_attachment
""" + WHERE_SQL + """
  GROUP BY checksum
    HAVING COUNT(*) > 1
"""
TOTALS_SQL_RECORD = (
    'SELECT COUNT(*), COALESCE(SUM(copies - 1), 0), '
    '       COALESCE(SUM(size * (copies - 1)), 0) '
    'FROM (' + GROUPED_SQL_RECORD + ') grouped')
TOTALS_SQL_GLOBAL = (
    'SELECT COUNT(*), COALESCE(SUM(copies - 1), 0), '
    '       COALESCE(SUM(size * (copies - 1)), 0) '
    'FROM (' + GROUPED_SQL_GLOBAL + ') grouped')
LISTED_SQL_RECORD = (
    'SELECT checksum, res_model, res_id FROM (' + GROUPED_SQL_RECORD + ') grouped '
    'ORDER BY size * (copies - 1) DESC, copies DESC, checksum LIMIT %s')
LISTED_SQL_GLOBAL = (
    'SELECT checksum, res_model, res_id FROM (' + GROUPED_SQL_GLOBAL + ') grouped '
    'ORDER BY size * (copies - 1) DESC, copies DESC, checksum LIMIT %s')


def format_bytes(size):
    """Human readable size; local on purpose so no odoo.tools helper is relied on."""
    size = float(size or 0.0)
    if size < 1024.0:
        return '%d B' % int(size)
    for unit in ('KB', 'MB', 'GB'):
        size /= 1024.0
        if size < 1024.0:
            return '%.1f %s' % (size, unit)
    return '%.1f TB' % (size / 1024.0)


class DuplicateAttachmentScan(models.TransientModel):
    _name = 'duplicate.attachment.scan'
    _description = 'Duplicate Attachment Scan'

    state = fields.Selection(
        [('draft', 'Not scanned yet'), ('done', 'Scanned')],
        string='Status', default='draft', readonly=True)
    scan_date = fields.Datetime(string='Scanned On', readonly=True)
    scope = fields.Selection(
        [('record', 'Same record only (recommended)'),
         ('global', 'Anywhere in the database')],
        string='Look For', default='record', required=True,
        help='Same record only: the same file attached several times to the '
             'same record. Removing the extra copies leaves every record with '
             'its file.\n'
             'Anywhere in the database: identical files wherever they are. Only '
             'one copy survives for the whole database, so the other records '
             'lose their link to the file.')
    min_size_kb = fields.Integer(
        string='Ignore Files Smaller Than (KB)', default=0,
        help='Files below this size are skipped. Leave 0 to look at every attachment.')
    group_limit = fields.Integer(
        string='Groups To List', default=200,
        help='How many duplicate groups are listed, biggest wins first (1000 at '
             'most). The totals always cover every group found, listed or not.')
    line_ids = fields.One2many(
        'duplicate.attachment.group', 'scan_id', string='Duplicate Files Found')
    group_count = fields.Integer(string='Duplicate Groups', readonly=True)
    listed_count = fields.Integer(string='Groups Listed', readonly=True)
    redundant_count = fields.Integer(string='Redundant Copies', readonly=True)
    wasted_bytes = fields.Float(string='Redundant Bytes', digits=(16, 0), readonly=True)
    wasted_display = fields.Char(string='Space In Redundant Copies', readonly=True)
    cleanup_message = fields.Char(string='Last Clean-up', readonly=True)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _compute_display_name(self):
        for scan in self:
            scan.display_name = _('Find Duplicate Attachments')

    def _min_bytes(self):
        return max(0, self.min_size_kb or 0) * 1024

    def _attachment_domain(self):
        """The attachments this module may look at: same filter as WHERE_SQL."""
        return [
            ('checksum', '!=', False),
            ('checksum', '!=', ''),
            # attachments that hold a binary field of a record: deleting them
            # empties that field, so they are out of scope entirely
            ('res_field', '=', False),
            ('file_size', '>', 0),
            ('file_size', '>=', self._min_bytes()),
            '|', ('res_model', '=', False),
            ('res_model', 'not in', list(EXCLUDED_MODELS)),
        ]

    def _sql_params(self):
        """Parameters of WHERE_SQL, matching _attachment_domain()."""
        return [tuple(EXCLUDED_MODELS), self._min_bytes()]

    def _flush_attachments(self):
        """Pending ORM writes must reach the table before the aggregate runs."""
        attachment = self.env['ir.attachment']
        if hasattr(attachment, 'flush_model'):
            attachment.flush_model()
        else:  # 14.0/15.0
            attachment.flush()

    def _check_cleanup_rights(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_(
                'Only Settings administrators may delete duplicate attachments.'))

    @api.model
    def _group_key(self, attachment, scope):
        """Two attachments belong to the same group when this key matches."""
        if scope == 'global':
            return ('', 0)
        return (attachment.res_model or '', attachment.res_id or 0)

    # ------------------------------------------------------------------
    # scan (report only)
    # ------------------------------------------------------------------
    def _run_scan(self):
        self.ensure_one()
        self._flush_attachments()
        params = self._sql_params()
        is_global = self.scope == 'global'
        self.env.cr.execute(TOTALS_SQL_GLOBAL if is_global else TOTALS_SQL_RECORD, params)
        group_count, redundant, wasted = self.env.cr.fetchone()

        limit = min(max(self.group_limit or 200, 1), MAX_LISTED_GROUPS)
        self.env.cr.execute(LISTED_SQL_GLOBAL if is_global else LISTED_SQL_RECORD,
                            params + [limit])
        keys = self.env.cr.fetchall()

        lines = self._group_values(keys)
        self.write({
            'state': 'done',
            'scan_date': fields.Datetime.now(),
            'group_count': group_count or 0,
            'redundant_count': redundant or 0,
            'wasted_bytes': float(wasted or 0),
            'wasted_display': format_bytes(wasted or 0),
            'listed_count': len(lines),
            'line_ids': [(5, 0, 0)] + [(0, 0, vals) for vals in lines],
        })

    def _group_values(self, keys):
        """One line per group, oldest copy first."""
        if not keys:
            return []
        scope = self.scope
        checksums = list({key[0] for key in keys})
        # sudo: the scan is restricted to Settings administrators and reports on
        # the whole database on purpose
        records = self.env['ir.attachment'].sudo().search(
            self._attachment_domain() + [('checksum', 'in', checksums)],
            order='create_date asc, id asc')
        grouped = {}
        for attachment in records:
            group = (attachment.checksum,) + self._group_key(attachment, scope)
            grouped.setdefault(group, []).append(attachment)

        values = []
        for checksum, res_model, res_id in keys:
            copies = grouped.get((checksum, res_model or '', res_id or 0)) or []
            if len(copies) < 2:
                continue
            keeper = copies[0]
            size = keeper.file_size or 0
            values.append({
                'checksum': checksum,
                'res_model': res_model or False,
                'res_id': res_id or 0,
                'file_name': keeper.name or _('Unnamed'),
                'file_size': float(size),
                'copy_count': len(copies),
                'wasted_bytes': float(size * (len(copies) - 1)),
                'wasted_display': format_bytes(size * (len(copies) - 1)),
                'location_summary': self._location_summary(copies),
                'keep_attachment_id': keeper.id,
                'keep_date': keeper.create_date,
                'selected': True,
            })
        return values

    @api.model
    def _location_summary(self, copies):
        counts = {}
        for attachment in copies:
            if attachment.res_model and attachment.res_id:
                key = '%s #%s' % (attachment.res_model, attachment.res_id)
            elif attachment.res_model:
                key = attachment.res_model
            else:
                key = _('Not linked to a record')
            counts[key] = counts.get(key, 0) + 1
        return ', '.join('%s (%s)' % (where, count) for where, count
                         in sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    def action_scan(self):
        """Report only: this button never deletes anything."""
        self.ensure_one()
        self.cleanup_message = False
        self._run_scan()
        return False

    def action_open_cleanup(self):
        """Open the confirmation dialog. Still nothing is deleted here."""
        self.ensure_one()
        self._check_cleanup_rights()
        if self.state != 'done':
            raise UserError(_('Run the scan before cleaning anything up.'))
        if not self.line_ids.filtered('selected'):
            raise UserError(_('Tick at least one duplicate group to clean up.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Confirm Clean-up'),
            'res_model': 'duplicate.attachment.clean',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_scan_id': self.id},
        }

    # ------------------------------------------------------------------
    # clean-up (explicitly confirmed)
    # ------------------------------------------------------------------
    def _group_copies(self, line):
        """The live copies of one reported group, oldest first."""
        copies = self.env['ir.attachment'].sudo().search(
            self._attachment_domain() + [('checksum', '=', line.checksum)],
            order='create_date asc, id asc')
        key = (line.res_model or '', line.res_id or 0)
        return copies.filtered(
            lambda a: self._group_key(a, self.scope) == key
            and a.checksum == line.checksum
            and not a.res_field
            and a.res_model not in EXCLUDED_MODELS)

    def _perform_cleanup(self):
        """Remove the redundant copies of the ticked groups, keeping the oldest.

        Everything is recomputed from the live table; the scan result only says
        which groups the user confirmed.
        """
        self.ensure_one()
        self._check_cleanup_rights()
        lines = self.line_ids.filtered('selected')
        if not lines:
            raise UserError(_('Tick at least one duplicate group to clean up.'))

        Attachment = self.env['ir.attachment']
        removed = groups = skipped = vanished = 0
        freed = 0.0
        for line in lines:
            copies = self._group_copies(line)
            if len(copies) < 2:
                continue  # already cleaned up, or the file is unique again
            keeper = copies[0]
            duplicates = (copies[1:] - keeper).exists()
            if not duplicates:
                continue
            size = keeper.file_size or 0
            count = len(duplicates)
            try:
                with self.env.cr.savepoint():
                    # no sudo: the standard ir.attachment access checks apply
                    for index in range(0, count, UNLINK_BATCH):
                        batch = duplicates.ids[index:index + UNLINK_BATCH]
                        Attachment.browse(batch).unlink()
            except AccessError:
                skipped += 1
                continue
            except MissingError:
                # somebody else deleted a copy while we were working
                vanished += 1
                continue
            if not keeper.exists():
                raise UserError(_('Aborted: the copy to keep disappeared for "%s".')
                                % (line.file_name or ''))
            removed += count
            freed += size * count
            groups += 1

        message = _('%(removed)s duplicate copy(ies) removed from %(groups)s group(s), '
                    '%(freed)s of redundant data. One copy of every file was kept.') % {
            'removed': removed, 'groups': groups, 'freed': format_bytes(freed)}
        if skipped:
            message += ' ' + _(
                '%s group(s) were left alone for lack of access rights.') % skipped
        if vanished:
            message += ' ' + _(
                '%s group(s) changed during the clean-up and were left alone; '
                'run the scan again.') % vanished
        self._run_scan()
        self.cleanup_message = message
        return message

    def action_view_result(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Find Duplicate Attachments'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            # 'main' replaces the breadcrumb instead of stacking a second page
            'target': 'main',
        }


class DuplicateAttachmentGroup(models.TransientModel):
    _name = 'duplicate.attachment.group'
    _description = 'Duplicate Attachment Group'
    _order = 'wasted_bytes desc, id'

    scan_id = fields.Many2one(
        'duplicate.attachment.scan', string='Scan', required=True, ondelete='cascade')
    selected = fields.Boolean(string='Clean Up', default=True)
    checksum = fields.Char(string='Checksum', readonly=True)
    res_model = fields.Char(string='Model', readonly=True)
    res_id = fields.Integer(string='Record ID', readonly=True)
    file_name = fields.Char(string='File', readonly=True)
    file_size = fields.Float(string='Size Of One Copy', digits=(16, 0), readonly=True)
    copy_count = fields.Integer(string='Copies', readonly=True)
    wasted_bytes = fields.Float(string='Redundant Bytes', digits=(16, 0), readonly=True)
    wasted_display = fields.Char(string='Redundant Space', readonly=True)
    location_summary = fields.Char(string='Attached To', readonly=True)
    keep_attachment_id = fields.Many2one(
        'ir.attachment', string='Copy Kept', readonly=True, ondelete='set null')
    keep_date = fields.Datetime(string='Oldest Copy', readonly=True)
