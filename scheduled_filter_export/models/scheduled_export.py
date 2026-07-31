# -*- coding: utf-8 -*-
# Part of scheduled_filter_export. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import base64
import calendar
import csv
import html
import io
import logging
import re

import pytz

from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import html_escape
from odoo.tools.misc import format_date, format_datetime
from odoo.tools.safe_eval import safe_eval

try:  # pragma: no cover - depends on what is installed on the server
    import xlsxwriter
except ImportError:  # pragma: no cover
    xlsxwriter = None

_logger = logging.getLogger(__name__)

#: Hard cap on the number of rows written into one file. It keeps the cron
#: transaction short and the attachment small enough to actually be delivered.
#: A truncated file says so on its last line and in the email body.
MAX_ROWS = 5000

#: Fields whose value cannot be put in a cell (see scheduled_export_line).
UNSUPPORTED_TTYPES = ('binary',)

#: Numeric field types written as numbers rather than text.
NUMERIC_TTYPES = ('integer', 'float', 'monetary')

MIMETYPES = {
    'csv': 'text/csv',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}

#: A leading one of these characters turns a spreadsheet cell into a formula.
#: Text values that start with one are prefixed with an apostrophe in CSV so a
#: contact called "=cmd|..." cannot execute anything in the recipient's Excel.
CSV_FORMULA_PREFIXES = ('=', '+', '@', '\t', '\r')

EMAIL_RE = re.compile(r'^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$')

WEEKDAYS = [
    ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'), ('3', 'Thursday'),
    ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday'),
]


class ScheduledExport(models.Model):
    _name = 'scheduled.export'
    _description = 'Scheduled Export by Email'
    _order = 'sequence, id'

    name = fields.Char(
        string='Export Name',
        required=True,
        help='Free label, e.g. "Monday customer list". It is used as the email '
             'subject and as the file name.',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(
        default=True,
        help='Uncheck to hide this export without deleting it. Archived '
             'exports are never run.',
    )
    enabled = fields.Boolean(
        string='Enabled',
        default=False,
        copy=False,
        help='Exports are created disabled on purpose. The scheduled action '
             'only runs exports that are explicitly enabled here.',
    )

    # --- what to export ------------------------------------------------
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain="[('transient', '=', False)]",
        help='The model whose records are exported, e.g. Contact or Sales '
             'Order.',
    )
    model_name = fields.Char(
        related='model_id.model',
        string='Model Name',
        store=True,
        readonly=True,
    )
    filter_domain = fields.Char(
        string='Filter',
        default='[]',
        help='Optional condition on the exported records. Leave empty to '
             'export every record the "Run As" user can see.',
    )
    line_ids = fields.One2many(
        'scheduled.export.line',
        'export_id',
        string='Columns',
        copy=True,
        help='The columns of the file, in order.',
    )

    # --- when ----------------------------------------------------------
    interval_type = fields.Selection(
        [('daily', 'Every day'),
         ('weekly', 'Every week'),
         ('monthly', 'Every month')],
        string='Frequency',
        default='daily',
        required=True,
    )
    weekday = fields.Selection(
        WEEKDAYS,
        string='Day of Week',
        default='0',
        help='Used by weekly exports only.',
    )
    day_of_month = fields.Integer(
        string='Day of Month',
        default=1,
        help='Used by monthly exports only. In a month that is shorter than '
             'the chosen day, the export runs on the last day of that month.',
    )
    hour_of_day = fields.Integer(
        string='Not Before (hour)',
        default=6,
        help='The export is sent at the first hourly check at or after this '
             'hour, in the timezone of the user it runs as.',
    )

    # --- how -----------------------------------------------------------
    def _default_run_as_user(self):
        """Whoever is creating the export, when that is a real person."""
        user = self.env.user
        if user.id == SUPERUSER_ID or not user.active or user.share:
            return self.env['res.users']
        return user

    run_as_user_id = fields.Many2one(
        'res.users',
        string='Run As',
        required=True,
        default=lambda self: self._default_run_as_user(),
        domain="[('share', '=', False)]",
        help='The export reads the records with this user\'s access rights and '
             'record rules: the recipients get exactly what this person is '
             'allowed to see. Only a Settings administrator can pick somebody '
             'else.',
    )
    recipient_ids = fields.Many2many(
        'res.partner',
        string='Recipients',
        help='Contacts the file is emailed to. Contacts without an email '
             'address are ignored.',
    )
    email_extra = fields.Char(
        string='Other Recipients',
        help='Extra email addresses, separated by commas, for people who are '
             'not contacts in Odoo.',
    )
    file_format = fields.Selection(
        [('csv', 'CSV'), ('xlsx', 'Excel (XLSX)')],
        string='File Format',
        default='csv',
        required=True,
        help='Excel needs the xlsxwriter library on the server. When it is '
             'missing the file is sent as CSV and the email says so.',
    )

    # --- bookkeeping ---------------------------------------------------
    last_run = fields.Datetime(string='Last Run', readonly=True, copy=False)
    last_run_rows = fields.Integer(
        string='Rows in Last File', readonly=True, copy=False)
    last_run_state = fields.Selection(
        [('never', 'Never run'),
         ('success', 'Sent'),
         ('empty', 'No record matched'),
         ('error', 'Failed')],
        string='Last Result',
        default='never',
        readonly=True,
        copy=False,
    )
    last_error = fields.Text(string='Last Error', readonly=True, copy=False)
    row_limit = fields.Integer(
        string='Row Limit',
        compute='_compute_row_limit',
        help='Maximum number of rows written into one file.',
    )

    def _compute_row_limit(self):
        for export in self:
            export.row_limit = MAX_ROWS

    # ------------------------------------------------------------------
    # Who may point an export at whom
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        exports = super().create(vals_list)
        exports._check_run_as_permission()
        return exports

    def write(self, vals):
        result = super().write(vals)
        if 'run_as_user_id' in vals:
            self._check_run_as_permission()
        return result

    def _check_run_as_permission(self):
        """Refuse an export pointed at a user the configurer cannot act as.

        Deliberately NOT an @api.constrains: 18.0 and 19.0 run constraint
        methods under sudo(), which would make every caller look like an
        administrator and quietly disable this check.
        """
        if self.env.su or self.env.user.has_group('base.group_system'):
            return
        for export in self:
            if export.run_as_user_id and export.run_as_user_id != self.env.user:
                raise AccessError(_(
                    'You can only schedule exports that run as yourself. '
                    'Running an export as "%s" would let you receive records '
                    'you are not allowed to read, so it is reserved to '
                    'Settings administrators.'
                ) % export.run_as_user_id.display_name)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @api.constrains('run_as_user_id')
    def _check_run_as_user(self):
        """The "Run As" user must be somebody an export can sanely read as:
        an active internal user, never a portal account and never the
        superuser, who would ignore every record rule."""
        for export in self:
            user = export.run_as_user_id
            if not user:
                raise ValidationError(_('Choose the user this export runs as.'))
            if user.share:
                raise ValidationError(_(
                    'An export cannot run as the portal or public user "%s". '
                    'Pick an internal user.'
                ) % user.display_name)
            if not user.active:
                raise ValidationError(_(
                    'The user "%s" is archived, an export cannot run as them.'
                ) % user.display_name)
            if user.id == SUPERUSER_ID:
                # The superuser ignores every record rule, which is exactly
                # what this module promises never to do.
                raise ValidationError(_(
                    'An export cannot run as the superuser: it would ignore '
                    'every record rule. Pick a real internal user.'))

    def _run_as_is_usable(self):
        """Can this export read anything as its "Run As" user at all?"""
        self.ensure_one()
        user = self.run_as_user_id
        return bool(user and user.active and not user.share
                    and user.id != SUPERUSER_ID)

    @api.constrains('model_id', 'filter_domain', 'run_as_user_id')
    def _check_model_and_filter(self):
        """A model that cannot be exported, or a filter that does not apply to
        it, must be refused while the user is looking at the form — not at
        six in the morning inside the cron where nobody sees it."""
        for export in self:
            if not export._run_as_is_usable():
                # _check_run_as_user says exactly what is wrong with the user;
                # a second, vaguer error on top of it only confuses.
                continue
            model = export._readable_model()
            domain = export._parse_filter_domain()
            try:
                model.search(domain, limit=1)
            except Exception as error:  # noqa: BLE001 - any failure = unusable
                raise ValidationError(_(
                    'The filter of "%(export)s" cannot be applied to '
                    '%(model)s as %(user)s: %(error)s'
                ) % {'export': export.name or '', 'model': export.model_name,
                     'user': export.run_as_user_id.display_name,
                     'error': error})

    @api.constrains('enabled', 'line_ids', 'recipient_ids', 'email_extra')
    def _check_ready_to_run(self):
        for export in self:
            if not export.enabled:
                continue
            if not export.line_ids:
                raise ValidationError(_(
                    'Add at least one column before enabling the export "%s".'
                ) % (export.name or ''))
            if not export._recipient_emails():
                raise ValidationError(_(
                    'The export "%s" has no recipient with an email address. '
                    'Add a contact that has an email, or type an address in '
                    '"Other Recipients".'
                ) % (export.name or ''))

    @api.constrains('email_extra')
    def _check_email_extra(self):
        for export in self:
            for address in export._split_addresses(export.email_extra):
                if not EMAIL_RE.match(address):
                    raise ValidationError(_(
                        '"%s" is not a valid email address. Separate several '
                        'addresses with commas.'
                    ) % address)

    @api.constrains('hour_of_day', 'day_of_month')
    def _check_schedule_values(self):
        for export in self:
            if not 0 <= export.hour_of_day <= 23:
                raise ValidationError(_(
                    '"Not Before (hour)" must be between 0 and 23.'))
            if export.interval_type == 'monthly' and not 1 <= export.day_of_month <= 31:
                raise ValidationError(_(
                    '"Day of Month" must be between 1 and 31.'))

    @api.onchange('model_id')
    def _onchange_model_id(self):
        """Columns of the previous model make no sense on the new one."""
        self.update({'line_ids': [(5, 0, 0)], 'filter_domain': '[]'})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _split_addresses(raw):
        return [part.strip() for part in re.split(r'[,;]', raw or '')
                if part.strip()]

    def _recipient_emails(self):
        """Every address the file is sent to, de-duplicated, order kept."""
        self.ensure_one()
        addresses = [partner.email.strip() for partner in self.recipient_ids
                     if partner.email and partner.email.strip()]
        addresses += self._split_addresses(self.email_extra)
        seen, unique = set(), []
        for address in addresses:
            key = address.lower()
            if key not in seen:
                seen.add(key)
                unique.append(address)
        return unique

    def _parse_filter_domain(self):
        """The filter as a domain list, or a ValidationError explaining why the
        text the user typed is not one."""
        self.ensure_one()
        raw = (self.filter_domain or '').strip() or '[]'
        try:
            domain = safe_eval(raw)
        except Exception as error:  # noqa: BLE001 - any eval problem is a bad domain
            raise ValidationError(_(
                'The filter of "%(export)s" is not a valid domain: %(error)s'
            ) % {'export': self.name or '', 'error': error})
        if (isinstance(domain, tuple) and len(domain) == 3
                and isinstance(domain[0], str)):
            # A single condition typed without its enclosing brackets. Spliced
            # in as-is it would become three separate domain elements.
            domain = [domain]
        if not isinstance(domain, (list, tuple)):
            raise ValidationError(_(
                'The filter of "%s" must be a domain list, for example '
                '[("customer_rank", ">", 0)].'
            ) % (self.name or ''))
        return list(domain)

    def _readable_model(self):
        """The exported model, bound to the "Run As" user.

        Everything the export reads goes through this recordset, so the user's
        groups and record rules decide what ends up in the file. There is no
        sudo() anywhere on this path on purpose.
        """
        self.ensure_one()
        user = self.run_as_user_id
        if not self._run_as_is_usable():
            raise UserError(_(
                'The export "%(export)s" cannot run as "%(user)s": pick an '
                'active internal user who is not the superuser.'
            ) % {'export': self.name or '',
                 'user': user.display_name if user else ''})
        name = self.model_name
        model = self.env.get(name)
        if model is None:
            raise UserError(_(
                'The model "%s" does not exist any more (its module may have '
                'been uninstalled).'
            ) % (name or '?'))
        if model._abstract or model._transient or not model._auto:
            raise UserError(_(
                'The model "%s" has no regular database table, its records '
                'cannot be exported.'
            ) % name)
        companies = user.company_ids.ids or (
            [user.company_id.id] if user.company_id else [])
        return self.env[name].with_user(user).with_context(
            lang=user.lang or 'en_US',
            tz=user.tz or 'UTC',
            allowed_company_ids=companies,
        )

    def _timezone(self):
        self.ensure_one()
        name = self.run_as_user_id.tz or self.env.user.tz or 'UTC'
        try:
            return pytz.timezone(name)
        except Exception:  # noqa: BLE001 - a broken tz must not stop the export
            _logger.warning('scheduled_filter_export: unknown timezone %r, '
                            'falling back to UTC.', name)
            return pytz.UTC

    def _localize(self, naive_utc):
        """A naive UTC datetime as an aware datetime in the run-as user's tz."""
        self.ensure_one()
        return pytz.UTC.localize(naive_utc).astimezone(self._timezone())

    # ------------------------------------------------------------------
    # Schedule
    # ------------------------------------------------------------------
    def _is_due(self, now=None):
        """Should this export run at ``now`` (a naive UTC datetime)?

        ``now`` is a parameter rather than a call to fields.Datetime.now() so
        the schedule can be tested without waiting for next Monday.
        """
        self.ensure_one()
        now = fields.Datetime.to_datetime(now) or fields.Datetime.now()
        local = self._localize(now)
        if local.hour < self.hour_of_day:
            return False
        if self.interval_type == 'weekly' and str(local.weekday()) != (self.weekday or '0'):
            return False
        if self.interval_type == 'monthly':
            last_day = calendar.monthrange(local.year, local.month)[1]
            # A "31st of the month" export still goes out in February.
            if local.day != min(max(self.day_of_month or 1, 1), last_day):
                return False
        if self.last_run and self._localize(self.last_run).date() >= local.date():
            return False
        return True

    # ------------------------------------------------------------------
    # Reading the rows
    # ------------------------------------------------------------------
    def _collect_columns(self, model):
        """Return (descriptions, field names, headings, dropped field names).

        fields_get() is the authority on what the run-as user may read: a field
        restricted to a group they are not in is simply not in it. Rather than
        crashing on such a column the export drops it and says so in the email.
        """
        self.ensure_one()
        descriptions = model.fields_get()
        names, headings, dropped = [], [], []
        for line in self.line_ids:
            fname = line.field_id.name
            if fname in names:
                continue
            description = descriptions.get(fname)
            if not description or description.get('type') in UNSUPPORTED_TTYPES:
                dropped.append(fname)
                continue
            names.append(fname)
            headings.append(line._column_label(descriptions))
        if not names:
            raise UserError(_(
                'None of the columns of "%(export)s" can be read on '
                '%(model)s as %(user)s.'
            ) % {'export': self.name or '', 'model': self.model_name,
                 'user': self.run_as_user_id.display_name})
        return descriptions, names, headings, dropped

    def _x2many_names(self, model, descriptions, names, rows):
        """{field name: {id: display name}} for the x2many columns.

        One batched read per column for every id of the whole result set — the
        rows themselves are never browsed one by one.
        """
        mapping = {}
        for fname in names:
            if descriptions[fname]['type'] not in ('one2many', 'many2many'):
                continue
            ids = set()
            for row in rows:
                ids.update(row.get(fname) or [])
            names_by_id = {}
            if ids:
                comodel = descriptions[fname].get('relation')
                try:
                    for record in model.env[comodel].browse(
                            sorted(ids)).read(['display_name']):
                        names_by_id[record['id']] = record['display_name']
                except Exception:  # noqa: BLE001 - unreadable co-records stay as ids
                    _logger.info('scheduled_filter_export: could not read the '
                                 'names behind column %r, exporting ids.', fname)
            mapping[fname] = names_by_id
        return mapping

    def _format_value(self, env, description, value, names_by_id, bool_labels):
        """One cell, rendered the way a person expects to read it."""
        ttype = description['type']
        if ttype == 'boolean':
            return bool_labels[0] if value else bool_labels[1]
        if value is None or value is False:
            return ''
        if ttype == 'many2one':
            # search_read hands over (id, display name) already.
            if isinstance(value, (list, tuple)) and len(value) > 1:
                return value[1]
            return str(value)
        if ttype in ('one2many', 'many2many'):
            return ', '.join(str((names_by_id or {}).get(rid, rid))
                             for rid in value)
        if ttype == 'selection':
            return dict(description.get('selection') or []).get(value, str(value))
        if ttype == 'date':
            return format_date(env, value)
        if ttype == 'datetime':
            return format_datetime(env, value, tz=self.run_as_user_id.tz or 'UTC')
        if ttype in NUMERIC_TTYPES:
            return value
        if ttype == 'html':
            return re.sub(r'\s+', ' ',
                          html.unescape(re.sub(r'<[^>]+>', ' ', value))).strip()
        return str(value)

    def _build_table(self, model, descriptions, names, rows):
        """Every cell of the file. Called on a recordset whose context lang is
        the run-as user's, so ``_()`` below renders in their language."""
        self.ensure_one()
        x2many = self._x2many_names(model, descriptions, names, rows)
        # Translated once instead of once per boolean cell.
        bool_labels = (_('Yes'), _('No'))
        return [
            [self._format_value(model.env, descriptions[fname], row.get(fname),
                                x2many.get(fname), bool_labels)
             for fname in names]
            for row in rows
        ]

    def _truncation_note(self, shown, total):
        return _('Truncated: only the first %(shown)s of %(total)s matching '
                 'records are listed above.') % {'shown': shown, 'total': total}

    # ------------------------------------------------------------------
    # Rendering the file
    # ------------------------------------------------------------------
    @staticmethod
    def _csv_safe(value):
        text = '' if value is None else str(value)
        if text[:1] in CSV_FORMULA_PREFIXES:
            # Neutralise a value the recipient's spreadsheet would run.
            return "'" + text
        return text

    def _render_csv(self, headings, table):
        stream = io.StringIO()
        writer = csv.writer(stream, delimiter=',', quoting=csv.QUOTE_MINIMAL,
                            lineterminator='\r\n')
        writer.writerow([self._csv_safe(head) for head in headings])
        for row in table:
            writer.writerow([self._csv_safe(cell) for cell in row])
        # utf-8-sig: without the BOM Excel mangles every accented character.
        return stream.getvalue().encode('utf-8-sig')

    def _render_xlsx(self, headings, table):
        stream = io.BytesIO()
        book = xlsxwriter.Workbook(stream, {'in_memory': True})
        # Excel refuses [ ] : * ? / \ in a sheet name and caps it at 31 chars.
        sheet_name = re.sub(r'[\[\]:*?/\\]', ' ', self.name or 'Export')[:31]
        sheet = book.add_worksheet(sheet_name.strip() or 'Export')
        bold = book.add_format({'bold': True})
        sheet.freeze_panes(1, 0)
        for column, head in enumerate(headings):
            sheet.write_string(0, column, str(head), bold)
            sheet.set_column(column, column, min(max(len(str(head)) + 4, 12), 50))
        for index, row in enumerate(table, start=1):
            for column, cell in enumerate(row):
                # write_string, never write(): a value that looks like a
                # formula must stay text in the recipient's Excel too.
                if isinstance(cell, bool):
                    sheet.write_string(index, column, str(cell))
                elif isinstance(cell, (int, float)):
                    sheet.write_number(index, column, cell)
                else:
                    sheet.write_string(index, column,
                                       '' if cell is None else str(cell))
        book.close()
        return stream.getvalue()

    def _render_file(self, headings, table):
        """Return (file name, bytes, format actually used, fallback note)."""
        self.ensure_one()
        file_format, note = self.file_format, ''
        if file_format == 'xlsx' and xlsxwriter is None:
            file_format = 'csv'
            note = _(
                'Excel was requested but the xlsxwriter library is not '
                'installed on this Odoo server, so the file is attached as '
                'CSV instead.')
        if file_format == 'xlsx':
            payload = self._render_xlsx(headings, table)
        else:
            payload = self._render_csv(headings, table)
        slug = re.sub(r'[^A-Za-z0-9_-]+', '_', self.name or 'export').strip('_')
        stamp = fields.Datetime.to_string(fields.Datetime.now()).replace(
            '-', '').replace(':', '').replace(' ', '_')[:13]
        filename = '%s_%s.%s' % (slug[:40] or 'export', stamp, file_format)
        return filename, payload, file_format, note

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def _email_body(self, row_count, total, truncated, dropped, note, file_format):
        self.ensure_one()
        facts = [
            _('Model: %s') % html_escape(self.model_id.display_name or self.model_name),
            _('Rows in the file: %s') % row_count,
            _('Run as: %s — the file contains exactly the records this user is '
              'allowed to see.') % html_escape(self.run_as_user_id.display_name),
            _('Format: %s') % file_format.upper(),
        ]
        body = '<p>%s</p><ul>%s</ul>' % (
            _('Here is the scheduled export <b>%s</b>.') % html_escape(self.name or ''),
            ''.join('<li>%s</li>' % fact for fact in facts),
        )
        if truncated:
            body += '<p><b>%s</b></p>' % (_(
                'Only the first %(shown)s of %(total)s matching records are in '
                'the file; the last line of the file repeats this. Narrow the '
                'filter down to get everything.'
            ) % {'shown': row_count, 'total': total})
        if dropped:
            body += '<p>%s</p>' % (_(
                'These columns were skipped because the "Run As" user cannot '
                'read them: %s.') % html_escape(', '.join(dropped)))
        if note:
            body += '<p>%s</p>' % html_escape(note)
        body += '<p style="color:#888;font-size:12px;">%s</p>' % _(
            'Sent automatically by Odoo (Scheduled Export by Email).')
        return body

    def _create_mail(self, filename, payload, file_format, body):
        self.ensure_one()
        # res_model/res_id point at the message so Odoo deletes the file along
        # with the mail once it has been sent: nothing is stored in Odoo.
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'datas': base64.b64encode(payload),
            'type': 'binary',
            'mimetype': MIMETYPES.get(file_format, 'application/octet-stream'),
            'res_model': 'mail.message',
            'res_id': 0,
        })
        values = {
            'subject': _('Scheduled export: %s') % (self.name or ''),
            'email_to': ','.join(self._recipient_emails()),
            'body_html': body,
            'attachment_ids': [(6, 0, attachment.ids)],
            'auto_delete': True,
        }
        sender = self.run_as_user_id.partner_id.email_formatted
        if sender:
            values['email_from'] = sender
            values['author_id'] = self.run_as_user_id.partner_id.id
        return self.env['mail.mail'].sudo().create(values)

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------
    def _run_export(self, now=None, force_send=False):
        """Build the file and queue the email. Returns the mail.mail, or False
        when nothing matched.

        No email is sent when the filter matches no record: the run is still
        recorded, so an export that has gone quiet is visible in the list
        instead of filling everyone's inbox with empty files.
        """
        self.ensure_one()
        now = fields.Datetime.to_datetime(now) or fields.Datetime.now()
        recipients = self._recipient_emails()
        if not recipients:
            raise UserError(_(
                'The export "%s" has no recipient with an email address.'
            ) % (self.name or ''))
        model = self._readable_model()
        # Headings, cell values, the file name and the email are all produced
        # in the run-as user's language, not the language of whoever (or
        # whatever cron) happens to trigger the run.
        localized = self.with_context(
            lang=model.env.context.get('lang') or 'en_US')
        descriptions, names, headings, dropped = localized._collect_columns(model)
        domain = self._parse_filter_domain()
        # search_count + a capped search_read: the table is never browsed.
        total = model.search_count(domain)
        rows = model.search_read(domain, names, limit=MAX_ROWS) if total else []
        if not rows:
            self.sudo().write({
                'last_run': now, 'last_run_rows': 0,
                'last_run_state': 'empty', 'last_error': False,
            })
            _logger.info('scheduled_filter_export: %r matched no record, no '
                         'email sent.', self.name)
            return False
        table = localized._build_table(model, descriptions, names, rows)
        truncated = total > len(rows)
        if truncated:
            note = localized._truncation_note(len(rows), total)
            table.append([note] + [''] * (len(headings) - 1))
        filename, payload, file_format, fallback = localized._render_file(
            headings, table)
        body = localized._email_body(len(rows), total, truncated, dropped,
                                     fallback, file_format)
        mail = localized._create_mail(filename, payload, file_format, body)
        if force_send:
            mail.send(raise_exception=False)
        self.sudo().write({
            'last_run': now, 'last_run_rows': len(rows),
            'last_run_state': 'success', 'last_error': False,
        })
        _logger.info('scheduled_filter_export: %r exported %s row(s) of %s to '
                     '%s.', self.name, len(rows), self.model_name,
                     ', '.join(recipients))
        return mail

    @api.model
    def _cron_run_exports(self, now=None):
        """Hourly entry point: run every enabled export that is due.

        sudo() on the search only: the scheduler has to see everybody's
        exports, but the records inside each file are still read as that
        export's own "Run As" user.
        """
        now = fields.Datetime.to_datetime(now) or fields.Datetime.now()
        exports = self.sudo().search([('enabled', '=', True)])
        ran = []
        for export in exports:
            try:
                # One savepoint per export: a broken model, an unreadable
                # filter or a mail failure must not cancel the others.
                with self.env.cr.savepoint():
                    if not export._is_due(now):
                        continue
                    if export._run_export(now=now):
                        ran.append(export.id)
            except Exception as error:  # noqa: BLE001 - keep going
                _logger.exception(
                    'scheduled_filter_export: export %r failed and was '
                    'skipped.', export.name)
                try:
                    # The failure itself is written outside the rolled-back
                    # savepoint, otherwise it would disappear with it.
                    with self.env.cr.savepoint():
                        export.sudo().write({
                            'last_run': now,
                            'last_run_rows': 0,
                            'last_run_state': 'error',
                            'last_error': str(error)[:2000],
                        })
                except Exception:  # noqa: BLE001
                    _logger.exception(
                        'scheduled_filter_export: could not record the failure '
                        'of export %r.', export.name)
        _logger.info('scheduled_filter_export: %s of %s enabled export(s) ran.',
                     len(ran), len(exports))
        return ran

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def action_run_now(self):
        """Build and send the file immediately, whatever the schedule says."""
        self.ensure_one()
        mail = self._run_export(force_send=True)
        if not mail:
            return self._notify(_(
                'No record matched the filter, so no email was sent.'),
                level='warning')
        return self._notify(_('%(rows)s row(s) sent to %(to)s.') % {
            'rows': self.last_run_rows,
            'to': ', '.join(self._recipient_emails()),
        }, level='success')

    def action_preview(self):
        """Open the records the next run would export. Sends nothing."""
        self.ensure_one()
        model = self._readable_model()
        domain = self._parse_filter_domain()
        records = model.search(domain, limit=MAX_ROWS)
        if not records:
            return self._notify(_(
                'No %s record matches this filter for %s.'
            ) % (self.model_id.display_name, self.run_as_user_id.display_name))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Preview: %s') % self.name,
            'res_model': self.model_name,
            'view_mode': 'list,form',
            'domain': [('id', 'in', records.ids)],
            'context': {'create': False},
            'target': 'current',
        }

    def _notify(self, message, level='info'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Scheduled Export'),
                'message': message,
                'type': level,
                'sticky': False,
            },
        }
