# -*- coding: utf-8 -*-
# Part of mail_blacklist_bulk_import. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import base64
import csv
import io
import logging
import re

from psycopg2.extensions import TransactionRollbackError

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Hard cap: one run never processes more than this many addresses. The wizard
# says so explicitly when the input is longer.
MAX_ADDRESSES = 1000
# Refuse oversized input before parsing it: the cap above bounds the addresses
# written, this bounds the bytes read.
MAX_INPUT_BYTES = 1024 * 1024
# Longest address accepted (RFC 5321 path limit).
MAX_EMAIL_LENGTH = 254
# Addresses may be separated by newlines, commas, semicolons or tabs.
SEPARATOR_RE = re.compile(r'[\r\n;,\t]+')
# Applied to the *normalized* address: local@labels.tld, no whitespace, and a
# dotted domain (so user@localhost is rejected rather than silently accepted).
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$')
# A leading column header in a pasted list is ignored.
HEADER_LABELS = {
    'address', 'e-mail', 'e-mail address', 'email', 'email address', 'emails',
    'mail', 'recipient',
}


class MailBlacklistBulkImport(models.TransientModel):
    _name = 'mail.blacklist.bulk.import'
    _description = 'Bulk Import Email Blacklist'

    mode = fields.Selection(
        [('add', 'Add to the blacklist'),
         ('remove', 'Remove from the blacklist')],
        string='Mode', default='add', required=True,
        help='Add blacklists the listed addresses. Remove un-blacklists them '
             '(Odoo archives the blacklist entry, it is never deleted).')
    source = fields.Selection(
        [('text', 'Paste addresses'),
         ('file', 'Upload a file')],
        string='Source', default='text', required=True)
    address_text = fields.Text(
        string='Email Addresses',
        help='One address per line, or several per line separated by a comma '
             'or a semicolon.')
    data_file = fields.Binary(string='File')
    file_name = fields.Char(string='File Name')
    max_addresses = fields.Integer(
        string='Addresses per Run', default=MAX_ADDRESSES, readonly=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Done')], default='draft', required=True)

    # --- results -----------------------------------------------------------
    found_count = fields.Integer(string='Found in Input', readonly=True)
    processed_count = fields.Integer(string='Processed', readonly=True)
    added_count = fields.Integer(string='Added', readonly=True)
    existing_count = fields.Integer(string='Already Blacklisted', readonly=True)
    removed_count = fields.Integer(string='Removed', readonly=True)
    missing_count = fields.Integer(string='Not Blacklisted', readonly=True)
    duplicate_count = fields.Integer(string='Duplicates in Input', readonly=True)
    invalid_count = fields.Integer(string='Invalid', readonly=True)
    truncated = fields.Boolean(string='Input Truncated', readonly=True)
    result_text = fields.Text(string='Result', readonly=True)
    invalid_text = fields.Text(
        string='Invalid Addresses', readonly=True,
        help='The rejected entries, one per line: fix them and run the import '
             'again on this list only.')

    # ------------------------------------------------------------------
    # Input parsing
    # ------------------------------------------------------------------
    @api.model
    def _check_input_size(self, length):
        if length > MAX_INPUT_BYTES:
            raise UserError(_(
                'The input is larger than %(mb)s MB. This wizard processes '
                '%(cap)s addresses per run, so please split it first.') % {
                    'mb': MAX_INPUT_BYTES // (1024 * 1024),
                    'cap': MAX_ADDRESSES})

    def _decode_file(self):
        """Decode the uploaded file, tolerating the usual export encodings."""
        self.ensure_one()
        try:
            content = base64.b64decode(self.data_file or b'')
        except (TypeError, ValueError) as err:
            raise UserError(_('The uploaded file could not be read: %s') % err)
        self._check_input_size(len(content))
        text = False
        if content[:2] in (b'\xff\xfe', b'\xfe\xff'):
            try:
                text = content.decode('utf-16')
            except UnicodeDecodeError:
                text = False
        if text is False:
            try:
                text = content.decode('utf-8-sig')
            except UnicodeDecodeError:
                # latin-1 maps every byte, so this never raises: a wrong file
                # simply yields entries that fail validation and are reported.
                text = content.decode('latin-1')
        # A UTF-16 file saved without a BOM decodes as UTF-8 riddled with NUL
        # characters, which csv.reader refuses outright on older Pythons.
        if '\x00' in text:
            text = text.replace('\x00', '')
        return text

    @api.model
    def _tokens_from_text(self, text):
        """Split pasted text into candidate addresses, in input order."""
        tokens = []
        for chunk in SEPARATOR_RE.split(text or ''):
            chunk = chunk.strip()
            if not chunk:
                continue
            # "Name <a@b.com>" is a single address; "a@b.com d@e.com" is two.
            if ' ' in chunk and not tools.email_normalize(chunk):
                tokens.extend(part for part in chunk.split() if part)
            else:
                tokens.append(chunk)
        return tokens

    @api.model
    def _tokens_from_csv(self, text):
        """One address per CSV row: the first cell holding an '@', else the
        first non-empty cell (so junk rows are reported, not skipped)."""
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t')
        except csv.Error:
            dialect = csv.excel
        rows = []
        try:
            for row in csv.reader(io.StringIO(text), dialect):
                cells = [cell.strip() for cell in row if cell and cell.strip()]
                if cells:
                    rows.append(cells)
        except csv.Error as err:
            # csv.reader raises while iterating (NUL bytes, a field over its
            # size limit): turn that into a message, never a traceback.
            raise UserError(_(
                'The CSV file could not be read (%s). Save it as UTF-8 CSV, '
                'or paste the addresses instead.') % err)
        # A header row carries no address at all while the rows below do.
        if len(rows) > 1 and not any('@' in cell for cell in rows[0]) \
                and any('@' in cell for cell in rows[1]):
            rows = rows[1:]
        tokens = []
        for cells in rows:
            with_at = [cell for cell in cells if '@' in cell]
            tokens.append(with_at[0] if with_at else cells[0])
        return tokens

    def _collect_tokens(self):
        """Return the candidate addresses read from the selected source."""
        self.ensure_one()
        if self.source == 'file':
            if not self.data_file:
                raise UserError(_('Upload a CSV or TXT file first.'))
            text = self._decode_file()
            if (self.file_name or '').lower().endswith('.csv'):
                tokens = self._tokens_from_csv(text)
            else:
                tokens = self._tokens_from_text(text)
        else:
            if not (self.address_text or '').strip():
                raise UserError(_('Paste at least one email address first.'))
            self._check_input_size(len(self.address_text))
            tokens = self._tokens_from_text(self.address_text)
        if tokens and '@' not in tokens[0] \
                and tokens[0].strip('"\' ').lower() in HEADER_LABELS:
            tokens = tokens[1:]
        if not tokens:
            raise UserError(_('No email address was found in the input.'))
        return tokens

    @api.model
    def _validate_address(self, raw):
        """Return (normalized_address, False) or (False, reason)."""
        candidate = (raw or '').strip()
        if not candidate:
            return False, _('empty entry')
        if len(candidate) > MAX_EMAIL_LENGTH:
            return False, _('longer than %s characters') % MAX_EMAIL_LENGTH
        normalized = tools.email_normalize(candidate)
        if not normalized:
            return False, _('not a valid email address')
        if not EMAIL_RE.match(normalized):
            return False, _('the domain needs a dot, as in example.com')
        return normalized, False

    # ------------------------------------------------------------------
    # Blacklist helpers
    # ------------------------------------------------------------------
    @api.model
    def _blacklist_add(self, blacklist, email):
        """Prefer core's own helper so its normalization and the chatter entry
        apply; a build without it gets the equivalent archive flip."""
        if hasattr(blacklist, '_add'):
            blacklist._add(email)
            return
        record = blacklist.with_context(active_test=False).search(
            [('email', '=', email)], limit=1)
        if record:
            record.action_unarchive()
        else:
            blacklist.create({'email': email})

    @api.model
    def _blacklist_remove(self, blacklist, email):
        """Un-blacklist through core's helper. Odoo archives the entry, so the
        history of the address is kept."""
        if hasattr(blacklist, '_remove'):
            blacklist._remove(email)
            return
        record = blacklist.with_context(active_test=False).search(
            [('email', '=', email)], limit=1)
        if record:
            record.action_archive()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_import(self):
        self.ensure_one()
        # Belt and braces: mail.blacklist itself is a base.group_system model,
        # and so is this wizard, but the guard keeps the message readable if
        # somebody widens the access rules.
        if not self.env.is_system():
            raise AccessError(_(
                'Only Settings administrators can bulk edit the email blacklist.'))
        if 'mail.blacklist' not in self.env:
            raise UserError(_(
                'The Email Blacklist is not available on this database.'))
        blacklist = self.env['mail.blacklist']

        tokens = self._collect_tokens()
        found = len(tokens)
        # The field is readonly, but never trust it to stay in range.
        limit = max(1, min(self.max_addresses or MAX_ADDRESSES, MAX_ADDRESSES))
        truncated = found > limit
        tokens = tokens[:limit]

        # Pass 1: normalize, validate and drop repeats without touching the DB.
        emails = []
        seen = set()
        duplicates = 0
        invalid = []
        for raw in tokens:
            normalized, reason = self._validate_address(raw)
            if not normalized:
                invalid.append(((raw or '').strip() or _('(empty)'), reason))
            elif normalized in seen:
                duplicates += 1
            else:
                seen.add(normalized)
                emails.append(normalized)

        # Pass 2: one query for the current state of every address, so the rows
        # that need no change cost nothing at all.
        current = {}
        if emails:
            current = {
                row['email']: row['active']
                for row in blacklist.with_context(active_test=False).search_read(
                    [('email', 'in', emails)], ['email', 'active'])
            }

        added = existing = removed = missing = 0
        for email in emails:
            active = current.get(email)
            if self.mode == 'add' and active:
                existing += 1
                continue
            if self.mode == 'remove' and not active:
                missing += 1
                continue
            # One savepoint per written address: a failure on a single row
            # rolls back that row only and the run carries on.
            try:
                with self.env.cr.savepoint():
                    if self.mode == 'add':
                        self._blacklist_add(blacklist, email)
                        added += 1
                    else:
                        self._blacklist_remove(blacklist, email)
                        removed += 1
            except (AccessError, TransactionRollbackError):
                # Not a row problem. A serialization failure or a deadlock kills
                # the whole transaction (the savepoint cannot rescue it) and an
                # access error is a configuration fault: both must surface
                # instead of being reported as a bad address.
                raise
            except Exception as err:  # pylint: disable=broad-except
                _logger.warning(
                    'Blacklist bulk import failed on %s', email, exc_info=True)
                invalid.append((email, (str(err) or err.__class__.__name__)[:200]))

        values = {
            'state': 'done',
            'found_count': found,
            'processed_count': added + existing + removed + missing,
            'added_count': added,
            'existing_count': existing,
            'removed_count': removed,
            'missing_count': missing,
            'duplicate_count': duplicates,
            'invalid_count': len(invalid),
            'truncated': truncated,
            'invalid_text': '\n'.join(address for address, _reason in invalid),
        }
        values['result_text'] = self._build_report(values, invalid, limit)
        self.write(values)
        return self._reopen()

    def _build_report(self, values, invalid, limit):
        """Plain-text summary shown on the result screen."""
        self.ensure_one()
        if self.mode == 'add':
            lines = [_('Adding to the blacklist')]
        else:
            lines = [_('Removing from the blacklist')]
        lines.append(_('Addresses found in the input: %s') % values['found_count'])
        if values['truncated']:
            lines.append(_(
                'Only the first %(limit)s were processed. Submit the remaining '
                'addresses in another run.') % {'limit': limit})
        lines.append('')
        if self.mode == 'add':
            lines.append(_('Added to the blacklist: %s') % values['added_count'])
            lines.append(_('Already blacklisted: %s') % values['existing_count'])
        else:
            lines.append(_('Removed from the blacklist: %s') % values['removed_count'])
            lines.append(_('Not blacklisted: %s') % values['missing_count'])
        lines.append(_('Listed more than once: %s') % values['duplicate_count'])
        lines.append(_('Invalid: %s') % values['invalid_count'])
        if invalid:
            lines.append('')
            lines.append(_('Invalid entries'))
            for address, reason in invalid:
                lines.append('  %s - %s' % (address, reason))
        return '\n'.join(lines)

    def action_retry_invalid(self):
        """Load the rejected entries back into the wizard so they can be fixed
        and submitted again."""
        self.ensure_one()
        if not self.invalid_text:
            raise UserError(_('There is no invalid address to fix.'))
        self.write({
            'state': 'draft',
            'source': 'text',
            'address_text': self.invalid_text,
            'data_file': False,
            'file_name': False,
            'result_text': False,
            'invalid_text': False,
            'found_count': 0,
            'processed_count': 0,
            'added_count': 0,
            'existing_count': 0,
            'removed_count': 0,
            'missing_count': 0,
            'duplicate_count': 0,
            'invalid_count': 0,
            'truncated': False,
        })
        return self._reopen()

    def action_view_blacklist(self):
        self.ensure_one()
        return self.env['ir.actions.act_window']._for_xml_id(
            'mail.mail_blacklist_action')

    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bulk Import Email Blacklist'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context),
        }
