# -*- coding: utf-8 -*-
# Part of failed_mail_bulk_retry. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import json
from datetime import datetime, time

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.mail_mail import MAX_BATCH, MAX_LINES, MAX_SEND_NOW


class FailedMailRetryWizard(models.TransientModel):
    _name = 'failed.mail.retry.wizard'
    _description = 'Retry Failed Emails in Bulk'

    # _rec_name defaults to 'name': without it the breadcrumb of this screen
    # reads "failed.mail.retry.wizard,1" on every supported series.
    name = fields.Char(
        string='Screen', readonly=True,
        default=lambda self: _('Failed Outgoing Emails'))
    state = fields.Selection(
        [('draft', 'To Do'), ('done', 'Done')],
        string='Status', default='draft', readonly=True,
        help='Switches to Done once a retry or a cancellation has been run, '
             'which is when the result summary is filled in.',
    )
    scope = fields.Selection(
        [('queue', 'Whole failed queue'), ('selection', 'Messages selected in the list')],
        string='Scope', default='queue', readonly=True,
        help='Whole failed queue: the screen was opened from the Settings '
             'menu and lists every message in Delivery Failed state. '
             'Messages selected in the list: it was opened from the Emails '
             'list with a selection, and only those messages are listed.',
    )
    # The ids the screen was opened on, kept as JSON so that reloading the list
    # never shrinks the scope to the rows that happen to fit on one page.
    scope_mail_ids = fields.Text(string='Selected Ids', readonly=True)
    line_ids = fields.One2many(
        'failed.mail.retry.line', 'wizard_id', string='Failed Messages')
    failed_total = fields.Integer(
        string='Failed Messages', readonly=True,
        help='Total number of messages in Delivery Failed state in the scope '
             'of this screen, whether or not they all fit on it.',
    )
    listed_count = fields.Integer(
        string='Listed', readonly=True,
        help='How many of them are shown below.',
    )
    oldest_age_days = fields.Integer(
        string='Oldest Failure (days)', readonly=True,
        help='Age of the oldest listed message, counted from the moment it '
             'was queued. Retrying it delivers it to the recipient today.',
    )
    line_notice = fields.Char(string='Notice', readonly=True)
    send_now = fields.Boolean(
        string='Send immediately', default=True,
        help='Try to deliver the re-queued messages right away and report the '
             'result. Messages are sent one at a time, which costs one '
             'connection to your mail server each, so at most %s per run are '
             'sent inside the request; the rest wait for the standard mail '
             'queue cron, which sends them in a single connection. Untick for '
             'large batches, or while the mail server is still unreachable — '
             'every attempt then has to time out first.' % MAX_SEND_NOW,
    )
    retry_since_date = fields.Date(
        string='Retry From Date',
        help='Used by the "Retry Since Date" button, on the whole failed queue '
             'only. Every message in Delivery Failed state queued on or after '
             'this date (in your timezone) is retried, including messages that '
             'are not listed below, up to %s per run. Odoo does not store the '
             'moment a message failed, so the date it was queued is used.' % MAX_BATCH,
    )
    result_summary = fields.Text(string='Result', readonly=True)
    requeued_count = fields.Integer(string='Re-queued', readonly=True)
    sent_count = fields.Integer(string='Delivered', readonly=True)
    failed_again_count = fields.Integer(string='Failed Again', readonly=True)
    still_queued_count = fields.Integer(string='Left In Queue', readonly=True)
    removed_count = fields.Integer(
        string='Removed From Queue', readonly=True,
        help='Messages Odoo deleted while processing them, because they are '
             'flagged auto-delete. That happens both when the server accepted '
             'the message and when it refused the address, so this screen '
             'cannot say which — they are never counted as delivered. The '
             'outcome is recorded on the document the message came from.',
    )
    cancelled_count = fields.Integer(string='Cancelled', readonly=True)
    skipped_count = fields.Integer(string='Skipped', readonly=True)
    error_count = fields.Integer(string='Errors', readonly=True)

    # ------------------------------------------------------------------
    # Loading the screen
    # ------------------------------------------------------------------
    @api.model
    def _fmbr_context_mail_ids(self):
        """Ids passed by the Action menu of the Emails list, if any."""
        if self.env.context.get('active_model') != 'mail.mail':
            return []
        active_ids = self.env.context.get('active_ids') or []
        if not active_ids and self.env.context.get('active_id'):
            active_ids = [self.env.context['active_id']]
        return list(active_ids)

    @api.model
    def _fmbr_collect(self):
        """What the screen must show for the current context.

        :return: (scope, scope_ids, failed_total, dropped_from_selection,
                  mails_to_list) — the listed messages are always the oldest
                  of the scope, never the first ones the client happened to
                  select.
        """
        Mail = self.env['mail.mail']
        active_ids = self._fmbr_context_mail_ids()
        if active_ids:
            # A selection can be huge ("select all" on a broken queue), so it
            # is capped — and what the cap left out is reported on screen.
            kept = active_ids[:MAX_BATCH]
            domain = Mail._fmbr_failed_domain() + [('id', 'in', kept)]
            total = Mail.search_count(domain)
            listed = Mail.search(domain, order='create_date asc, id asc',
                                 limit=MAX_LINES)
            return 'selection', kept, total, len(active_ids) - len(kept), listed
        domain = Mail._fmbr_failed_domain()
        total = Mail.search_count(domain)
        listed = Mail.search(domain, order='create_date asc, id asc', limit=MAX_LINES)
        return 'queue', [], total, 0, listed

    def _fmbr_scope_ids(self):
        """The ids this screen was opened on ('selection' scope only)."""
        self.ensure_one()
        try:
            return json.loads(self.scope_mail_ids or '[]')
        except ValueError:  # pragma: no cover - defensive
            return []

    def _fmbr_scope_domain(self):
        """Domain of the failed messages this screen is allowed to act on."""
        self.ensure_one()
        domain = self.env['mail.mail']._fmbr_failed_domain()
        if self.scope == 'selection':
            domain = domain + [('id', 'in', self._fmbr_scope_ids())]
        return domain

    @api.model
    def _fmbr_line_values(self, mails, selected):
        """Line values for *mails*, oldest first."""
        return [{
            'mail_id': data['id'],
            'selected': selected,
            'subject': data['subject'],
            'recipient': data['recipient'],
            'age_days': data['age_days'],
            'queued_on': data['queued_on'],
            'last_attempt': data['last_attempt'],
            'failure_reason': data['failure_reason'],
        } for data in mails._fmbr_describe()]

    @api.model
    def _fmbr_notice(self, scope, failed_total, listed, dropped=0):
        """The plain-language status line shown above the list."""
        parts = []
        if not failed_total:
            parts.append(
                _('None of the messages you selected is in Delivery Failed '
                  'state, so there is nothing to retry here.')
                if scope == 'selection' else
                _('No message is in Delivery Failed state — the outgoing mail '
                  'queue is healthy.'))
        elif listed < failed_total and scope == 'selection':
            # "Retry Since Date" must NOT be suggested here: it works on the
            # whole queue, not on the selection.
            parts.append(_('Showing %(listed)s of the %(total)s failed messages '
                           'you selected. Retry them, then use "Refresh List" '
                           'to load the next ones.')
                         % {'listed': listed, 'total': failed_total})
        elif listed < failed_total:
            parts.append(_('Showing the %(listed)s oldest of %(total)s failed '
                           'messages. Use "Retry Since Date" to cover the ones '
                           'that are not listed.')
                         % {'listed': listed, 'total': failed_total})
        elif scope == 'selection':
            parts.append(_('%s selected message(s) are in Delivery Failed state.')
                         % failed_total)
        else:
            parts.append(_('%s message(s) are waiting in Delivery Failed state.')
                         % failed_total)
        if dropped:
            parts.append(_('Your selection was larger than %(cap)s messages: '
                           '%(dropped)s of them were left out. Use Settings > '
                           'Retry Failed Emails to work through the whole '
                           'queue instead.')
                         % {'cap': MAX_BATCH, 'dropped': dropped})
        return ' '.join(parts)

    @api.model
    def default_get(self, fields_list):
        res = super(FailedMailRetryWizard, self).default_get(fields_list)
        scope, scope_ids, failed_total, dropped, mails = self._fmbr_collect()
        # A selection was made on purpose by the administrator, so it is
        # pre-ticked; the whole queue never is — nothing is retried by accident.
        values = self._fmbr_line_values(mails, scope == 'selection')
        res.update({
            'scope': scope,
            'scope_mail_ids': json.dumps(scope_ids),
            'failed_total': failed_total,
            'listed_count': len(values),
            'oldest_age_days': max([v['age_days'] for v in values] or [0]),
            'line_notice': self._fmbr_notice(scope, failed_total, len(values), dropped),
            'line_ids': [(0, 0, vals) for vals in values],
        })
        return res

    @api.model
    def action_open(self):
        """Create the screen server-side and open it.

        The record is created here rather than by the form view so that the
        list of failed messages is built by ``default_get`` on the server and
        the browser never has to send it back: the administrator only ever
        writes the tick boxes.
        """
        return self.create({})._fmbr_reload_action()

    def _fmbr_refresh_lines(self):
        """Reload the list from the database, keeping the original scope.

        The scope comes from the ids the screen was opened on, never from the
        rows currently listed: retrying the first page must not make the rest
        of a large selection unreachable.
        """
        self.ensure_one()
        Mail = self.env['mail.mail']
        domain = self._fmbr_scope_domain()
        failed_total = Mail.search_count(domain)
        mails = Mail.search(domain, order='create_date asc, id asc', limit=MAX_LINES)
        values = self._fmbr_line_values(mails, False)
        self.write({
            'failed_total': failed_total,
            'listed_count': len(values),
            'oldest_age_days': max([v['age_days'] for v in values] or [0]),
            'line_notice': self._fmbr_notice(self.scope, failed_total, len(values)),
            'line_ids': [(5, 0, 0)] + [(0, 0, vals) for vals in values],
        })

    def _fmbr_reload_action(self):
        """Reopen this very screen, so the caller sees the refreshed list.

        ``target='main'`` on purpose: every button reopens the screen, and
        'current' would stack one breadcrumb per click.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Retry Failed Emails'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'main',
        }

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    def _fmbr_store_result(self, counters):
        """Write the counters and the human summary on the wizard."""
        self.ensure_one()
        lines = []
        if counters.get('requeued'):
            lines.append(_('%s message(s) put back in the sending queue.')
                         % counters['requeued'])
        if counters.get('sent'):
            lines.append(_('%s of them were delivered.') % counters['sent'])
        if counters.get('failed_again'):
            lines.append(_('%s failed again immediately — the mail server is '
                           'still refusing them. Open the message to read the '
                           'new error.') % counters['failed_again'])
        if counters.get('removed'):
            lines.append(_('%s message(s) were removed from the queue by Odoo '
                           'while it processed them, because they are flagged '
                           'auto-delete. Odoo does that both when the server '
                           'accepted the message and when it refused the '
                           'address, so they are NOT counted as delivered — '
                           'the outcome is recorded on the document each '
                           'message came from.') % counters['removed'])
        if counters.get('still_queued'):
            lines.append(_('%s are waiting in the queue and will be sent by '
                           'the "Email Queue Manager" scheduled action.')
                         % counters['still_queued'])
        if counters.get('send_now_left'):
            lines.append(_('Immediate sending is limited to %(cap)s message(s) '
                           'per run, so %(left)s were re-queued without being '
                           'sent here.') % {'cap': MAX_SEND_NOW,
                                            'left': counters['send_now_left']})
        if counters.get('cancelled'):
            lines.append(_('%s message(s) marked as Cancelled — they will '
                           'never be sent.') % counters['cancelled'])
        if counters.get('skipped'):
            lines.append(_('%s message(s) were skipped because they are no '
                           'longer in Delivery Failed state (already sent, '
                           'cancelled or deleted meanwhile).')
                         % counters['skipped'])
        if counters.get('errors'):
            lines.append(_('%s message(s) could not be processed at all; the '
                           'rest of the batch was unaffected. See the server '
                           'log for the details.') % counters['errors'])
        if not lines:
            lines.append(_('Nothing to do: no message in the selection is in '
                           'Delivery Failed state.'))
        self.write({
            'state': 'done',
            'requeued_count': counters.get('requeued', 0),
            'sent_count': counters.get('sent', 0),
            'failed_again_count': counters.get('failed_again', 0),
            'still_queued_count': counters.get('still_queued', 0),
            'removed_count': counters.get('removed', 0),
            'cancelled_count': counters.get('cancelled', 0),
            'skipped_count': counters.get('skipped', 0),
            'error_count': counters.get('errors', 0),
            'result_summary': '\n'.join(lines),
        })

    def _fmbr_selected_mails(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda line: line.selected)
        if not lines:
            raise UserError(_('Tick the messages you want to act on first.'))
        return lines.mapped('mail_id')

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def action_select_all(self):
        self.ensure_one()
        self.line_ids.write({'selected': True})
        return self._fmbr_reload_action()

    def action_select_none(self):
        self.ensure_one()
        self.line_ids.write({'selected': False})
        return self._fmbr_reload_action()

    def action_refresh(self):
        self.ensure_one()
        self._fmbr_refresh_lines()
        self.write({'state': 'draft', 'result_summary': False})
        return self._fmbr_reload_action()

    def action_retry_selected(self):
        """Re-queue (and optionally send) the ticked messages."""
        self.ensure_one()
        counters = self._fmbr_selected_mails()._fmbr_retry(send_now=self.send_now)
        self._fmbr_store_result(counters)
        self._fmbr_refresh_lines()
        return self._fmbr_reload_action()

    def action_retry_since(self):
        """Re-queue every failed message queued on or after the chosen date.

        Whole-queue only. Offering it on a selection would mail messages the
        administrator did not select, which is the one thing this screen must
        never do.
        """
        self.ensure_one()
        if self.scope == 'selection':
            raise UserError(_(
                '"Retry Since Date" works on the whole failed queue, not on a '
                'selection: it would send messages you did not select. Use '
                '"Retry Selected" here, or open Settings > Retry Failed Emails '
                'to work on the whole queue.'))
        if not self.retry_since_date:
            raise UserError(_('Choose the date to retry from first.'))
        Mail = self.env['mail.mail']
        mails = Mail.search(
            Mail._fmbr_failed_domain(since=self._fmbr_since_utc()),
            order='create_date asc, id asc', limit=MAX_BATCH)
        counters = mails._fmbr_retry(send_now=self.send_now)
        if len(mails) == MAX_BATCH:
            counters['truncated'] = True
        self._fmbr_store_result(counters)
        if counters.get('truncated'):
            self.write({'result_summary': '%s\n%s' % (
                self.result_summary,
                _('The %s message limit for one run was reached: run the same '
                  'retry again to continue with the next batch.') % MAX_BATCH)})
        self._fmbr_refresh_lines()
        return self._fmbr_reload_action()

    def action_cancel_selected(self):
        """Mark the ticked messages as Cancelled: they will never be sent."""
        self.ensure_one()
        counters = self._fmbr_selected_mails()._fmbr_cancel()
        self._fmbr_store_result(counters)
        self._fmbr_refresh_lines()
        return self._fmbr_reload_action()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _fmbr_since_utc(self):
        """Start of ``retry_since_date`` in the user's timezone, as naive UTC.

        create_date is stored in UTC; the administrator picked a calendar day
        in their own timezone.
        """
        self.ensure_one()
        naive = datetime.combine(self.retry_since_date, time.min)
        try:
            user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        except pytz.UnknownTimeZoneError:  # pragma: no cover - defensive
            user_tz = pytz.UTC
        return user_tz.localize(naive).astimezone(pytz.UTC).replace(tzinfo=None)


class FailedMailRetryLine(models.TransientModel):
    _name = 'failed.mail.retry.line'
    _description = 'Failed Email To Retry'
    _order = 'age_days desc, id asc'

    wizard_id = fields.Many2one(
        'failed.mail.retry.wizard', string='Wizard',
        required=True, ondelete='cascade', index=True)
    mail_id = fields.Many2one(
        'mail.mail', string='Message', required=True, ondelete='cascade',
        help='The queued email this line reports on.')
    selected = fields.Boolean(
        string='Selected', default=False,
        help='Tick the messages the buttons at the top should act on.')
    subject = fields.Char(string='Subject', readonly=True)
    recipient = fields.Char(
        string='Recipient', readonly=True,
        help='The address the message was sent to, or the recipient partners '
             'when Odoo resolves them itself.')
    age_days = fields.Integer(
        string='Age (days)', readonly=True,
        help='Days since the message was queued. Retrying an old message '
             'delivers it to the recipient today.',
    )
    queued_on = fields.Datetime(string='Queued On', readonly=True)
    last_attempt = fields.Datetime(
        string='Last Change', readonly=True,
        help='When Odoo last wrote to this message — normally the last '
             'delivery attempt.',
    )
    failure_reason = fields.Char(
        string='Failure Reason', readonly=True,
        help='First line of the error the mail server returned.',
    )
