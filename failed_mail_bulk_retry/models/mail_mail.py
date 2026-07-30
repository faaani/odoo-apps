# -*- coding: utf-8 -*-
# Part of failed_mail_bulk_retry. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# The ONLY state this module ever touches. Everything else is left alone on
# purpose:
#   'sent'     — re-sending would deliver a duplicate to the recipient;
#   'outgoing' — the standard "Email Queue Manager" cron is going to send it;
#   'cancel'   — somebody decided it must never leave, and this screen must not
#                silently resurrect it (use the Retry button on the message).
FAILED_STATE = 'exception'

# Hard caps. A mail queue after a long outage can hold tens of thousands of
# rows; a screen or a request that tries to swallow all of them at once times
# out. Every cap is reported in the UI when it is reached.
MAX_LINES = 300       # failed messages materialised on the screen
MAX_BATCH = 1000      # messages one "retry since date" run may re-queue
# Messages one run tries to deliver inside the request. Kept deliberately low:
# core's send() opens one SMTP connection per call and this module calls it once
# per message (see _fmbr_retry for why), so this is also a connection count.
MAX_SEND_NOW = 50

RECIPIENT_MAX = 120   # characters kept of the recipient list
REASON_MAX = 200      # characters kept of the mail server error


class MailMail(models.Model):
    _inherit = 'mail.mail'

    # ------------------------------------------------------------------
    # Selecting failed messages
    # ------------------------------------------------------------------
    @api.model
    def _fmbr_failed_domain(self, since=None):
        """Domain of the messages this module is allowed to work on.

        :param since: optional naive UTC datetime; only messages queued on or
            after that moment are matched.
        """
        domain = [('state', '=', FAILED_STATE)]
        if since:
            domain.append(('create_date', '>=', since))
        return domain

    def _fmbr_eligible(self):
        """The subset of ``self`` that is really in Delivery Failed state."""
        return self.exists().filtered(lambda mail: mail.state == FAILED_STATE)

    # ------------------------------------------------------------------
    # Display data
    # ------------------------------------------------------------------
    def _fmbr_describe(self):
        """Screen data for ``self``: one dict per message, oldest first.

        Read with a single ``search_read`` plus a single batched read of the
        recipient partners — never a browse per row.
        """
        if not self:
            return []
        rows = self.search_read(
            [('id', 'in', self.ids)],
            ['subject', 'email_to', 'recipient_ids',
             'create_date', 'write_date', 'failure_reason'],
            order='create_date asc, id asc',
        )
        partner_ids = set()
        for row in rows:
            partner_ids.update(row.get('recipient_ids') or [])
        partner_label = {}
        if partner_ids:
            for partner in self.env['res.partner'].browse(
                    sorted(partner_ids)).read(['email', 'display_name']):
                partner_label[partner['id']] = (
                    partner['email'] or partner['display_name'] or '')

        now = fields.Datetime.now()
        described = []
        for row in rows:
            created = fields.Datetime.to_datetime(row.get('create_date'))
            recipients = row.get('email_to') or ', '.join(
                label for label in (
                    partner_label.get(pid) for pid in (row.get('recipient_ids') or []))
                if label)
            reason = (row.get('failure_reason') or '').strip()
            reason = reason.splitlines()[0] if reason else ''
            described.append({
                'id': row['id'],
                'subject': (row.get('subject') or '')[:200],
                'recipient': recipients[:RECIPIENT_MAX],
                'age_days': max(0, (now - created).days) if created else 0,
                'queued_on': created,
                'last_attempt': fields.Datetime.to_datetime(row.get('write_date')),
                'failure_reason': reason[:REASON_MAX],
            })
        return described

    # ------------------------------------------------------------------
    # Bulk actions
    # ------------------------------------------------------------------
    def _fmbr_mark_outgoing(self, counters):
        """Re-queue every message of ``self`` with core's ``mark_outgoing()``.

        Writing a state cannot half-succeed against a mail server, so the whole
        batch is written in one statement first — a thousand savepoints for a
        thousand state writes is what makes a large recovery time out. If that
        write fails for any reason, every message is retried inside its own
        savepoint so one bad row still cannot cost the batch.

        :return: the ids that are now in 'outgoing' state.
        """
        try:
            with self.env.cr.savepoint():
                self.mark_outgoing()
            return list(self.ids)
        except Exception:  # noqa: BLE001 — fall back to one message at a time
            _logger.exception(
                'failed_mail_bulk_retry: bulk re-queue failed, retrying the '
                '%s message(s) one at a time', len(self))
        requeued_ids = []
        for mail in self:
            try:
                with self.env.cr.savepoint():
                    mail.mark_outgoing()
            except Exception:  # noqa: BLE001 — one message must not kill the batch
                _logger.exception(
                    'failed_mail_bulk_retry: could not re-queue mail %s', mail.id)
                counters['errors'] += 1
                continue
            requeued_ids.append(mail.id)
        return requeued_ids

    def _fmbr_retry(self, send_now=True):
        """Put the failed messages of ``self`` back in the sending queue.

        Uses Odoo's own ``mark_outgoing()`` and ``send()``; no hand-rolled
        SMTP. Sending is done one message at a time, each inside its own
        savepoint, so one bad recipient address rolls back that message only
        and the batch carries on.

        :param send_now: also try to deliver the re-queued messages inside
            this request (capped at MAX_SEND_NOW). When False the messages
            simply wait for the standard mail queue cron.
        :return: dict of counters, all of them real counts of what happened.
        """
        counters = {
            'requeued': 0, 'sent': 0, 'failed_again': 0, 'still_queued': 0,
            'removed': 0, 'skipped': 0, 'errors': 0, 'send_now_left': 0,
        }
        eligible = self._fmbr_eligible()
        counters['skipped'] = len(self) - len(eligible)
        if not eligible:
            return counters

        requeued_ids = eligible._fmbr_mark_outgoing(counters)
        counters['requeued'] = len(requeued_ids)
        requeued = self.browse(requeued_ids)

        if send_now and requeued:
            to_send = requeued[:MAX_SEND_NOW]
            counters['send_now_left'] = len(requeued) - len(to_send)
            for mail in to_send:
                # One send() and one savepoint per message on purpose. Core
                # only rolls its own failures back per message; a batch that
                # raises half way through would roll back messages the SMTP
                # server has already accepted, and the queue cron would then
                # deliver them a second time. A duplicate email in a customer's
                # inbox is worse than an extra SMTP connection, so the cost is
                # paid here and MAX_SEND_NOW is kept small.
                try:
                    with self.env.cr.savepoint():
                        # core's own send path; it records its own failures
                        mail.send(raise_exception=False)
                except Exception:  # noqa: BLE001 — one message must not kill the batch
                    _logger.exception(
                        'failed_mail_bulk_retry: sending mail %s failed', mail.id)
                    counters['errors'] += 1

        # Report the state the messages are actually in now.
        alive = requeued.exists()
        # Messages that are gone were deleted by Odoo itself: it removes a mail
        # flagged auto_delete as soon as it has processed it — both when the
        # server accepted it and when it refused the address
        # (mail.mail._postprocess_sent_message). Their outcome cannot be read
        # back from the queue, so they are reported on their own line and are
        # never counted as delivered.
        counters['removed'] = len(requeued) - len(alive)
        for mail in alive:
            if mail.state == 'sent':
                counters['sent'] += 1
            elif mail.state == FAILED_STATE:
                counters['failed_again'] += 1
            else:
                counters['still_queued'] += 1
        return counters

    def _fmbr_cancel(self):
        """Mark the failed messages of ``self`` as Cancelled, one savepoint each."""
        counters = {'cancelled': 0, 'skipped': 0, 'errors': 0}
        eligible = self._fmbr_eligible()
        counters['skipped'] = len(self) - len(eligible)
        for mail in eligible:
            try:
                with self.env.cr.savepoint():
                    mail.cancel()  # core's own Cancel: state -> 'cancel'
            except Exception:  # noqa: BLE001 — one message must not kill the batch
                _logger.exception(
                    'failed_mail_bulk_retry: could not cancel mail %s', mail.id)
                counters['errors'] += 1
                continue
            counters['cancelled'] += 1
        return counters
