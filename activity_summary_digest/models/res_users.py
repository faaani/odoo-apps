# -*- coding: utf-8 -*-
# Part of activity_summary_digest. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
from collections import OrderedDict

import pytz

from odoo import _, api, fields, models, release
from odoo.exceptions import AccessError
from odoo.tools import format_date, html_escape, str2bool

_logger = logging.getLogger(__name__)

PARAM_ENABLED = 'activity_summary_digest.enabled'
OPTIN_FIELD = 'activity_digest_optin'

# Hard bounds: a digest must never build a multi-megabyte email, however many
# activities one person managed to accumulate.
FETCH_LIMIT = 500
MAX_ROWS = 100


class ResUsers(models.Model):
    _inherit = 'res.users'

    activity_digest_optin = fields.Boolean(
        string='Daily Activity Digest',
        default=False,
        help='Receive one email every morning listing your activities that are '
             'due today or overdue. Nothing is sent on days you have none.',
    )

    def _register_hook(self):
        """Let every user switch their own digest on and off.

        14.0/15.0 keep SELF_*_FIELDS as plain class lists while 16.0+ expose
        them as properties; assigning a plain list on the registry class
        shadows either shape safely.
        """
        res = super(ResUsers, self)._register_hook()
        users = self.env['res.users']
        cls = type(users)
        for attr in ('SELF_READABLE_FIELDS', 'SELF_WRITEABLE_FIELDS'):
            current = list(getattr(users, attr, []) or [])
            if OPTIN_FIELD not in current:
                setattr(cls, attr, current + [OPTIN_FIELD])
        return res

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------
    @api.model
    def _activity_digest_enabled(self):
        """Global on/off switch. Read explicitly: get_param() hands back the
        default for any falsy stored value, so a default-True boolean bound
        with config_parameter= could never be switched off."""
        raw = self.env['ir.config_parameter'].sudo().get_param(PARAM_ENABLED, 'True')
        try:
            return str2bool(raw)
        except ValueError:
            return True

    # ------------------------------------------------------------------
    # collecting one user's activities
    # ------------------------------------------------------------------
    @api.model
    def _activity_digest_today(self, user):
        """The current calendar date **in the recipient's timezone**.

        mail.activity.date_deadline is a Date, so "due today" depends entirely
        on which date it currently is where the recipient sits: at the same
        instant two users can legitimately be on two different days.
        """
        tzname = user.tz or 'UTC'
        try:
            tz = pytz.timezone(tzname)
        except pytz.UnknownTimeZoneError:
            _logger.warning('Activity digest: unknown timezone %r for user %s, '
                            'falling back to UTC.', tzname, user.login)
            tz = pytz.UTC
        return pytz.UTC.localize(fields.Datetime.now()).astimezone(tz).date()

    @api.model
    def _activity_digest_rows(self, user, res_model, activities, base_url, today):
        """Digest rows for the activities of one document model.

        A single search per model applies that model's access rights and record
        rules **as the recipient**: ids the search does not give back are either
        gone (the record was deleted underneath the activity) or no longer
        readable, and are dropped from the digest.
        """
        if not res_model or res_model not in self.env:
            return []
        Model = self.env[res_model]
        if Model._abstract or Model._transient:
            return []
        res_ids = [act.res_id for act in activities if act.res_id]
        if not res_ids:
            return []
        try:
            records = Model.with_user(user).with_context(active_test=False).search(
                [('id', 'in', res_ids)])
            names = {record.id: record.display_name for record in records}
        except Exception:  # noqa: BLE001 - one odd model must not kill the digest
            _logger.warning('Activity digest: skipping model %r for user %s.',
                            res_model, user.login, exc_info=True)
            return []
        rows = []
        for act in activities:
            if act.res_id not in names:
                continue
            rows.append({
                'name': names[act.res_id] or _('Untitled'),
                'url': self._activity_digest_record_url(base_url, res_model, act.res_id),
                'activity_type': act.activity_type_id.display_name or _('Activity'),
                'summary': act.summary or '',
                'deadline': act.date_deadline,
                'overdue': bool(act.date_deadline and act.date_deadline < today),
            })
        return rows

    @api.model
    def _activity_digest_record_url(self, base_url, res_model, res_id):
        """Direct link to a record's form view (18.0 introduced /odoo/...)."""
        if release.version_info[0] >= 18:
            return '%s/odoo/%s/%s' % (base_url, res_model, res_id)
        return '%s/web#id=%s&model=%s&view_type=form' % (base_url, res_id, res_model)

    @api.model
    def _activity_digest_collect(self, user):
        """Everything the digest of `user` needs, or None when there is nothing
        to send. Returning None is what keeps empty digests from being sent."""
        today = self._activity_digest_today(user)
        Activity = self.env['mail.activity'].with_user(user)
        # only what this user is actually assigned, due today or earlier
        domain = [('user_id', '=', user.id), ('date_deadline', '<=', today)]
        activities = Activity.search(domain, order='date_deadline asc, id asc',
                                     limit=FETCH_LIMIT)
        if not activities:
            return None
        by_model = OrderedDict()
        for act in activities:
            by_model.setdefault(act.res_model, []).append(act)
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        groups = []
        for res_model, model_activities in by_model.items():
            rows = self._activity_digest_rows(
                user, res_model, model_activities, base_url, today)
            if rows:
                groups.append({
                    'model_label': self._activity_digest_model_label(res_model),
                    'rows': rows,
                })
        if not groups:
            return None
        count = sum(len(group['rows']) for group in groups)
        # the fetch itself is capped too: hitting FETCH_LIMIT means there may
        # well be more activities than the ones we looked at
        truncated = count > MAX_ROWS or len(activities) == FETCH_LIMIT
        if count > MAX_ROWS:
            capped, count = [], 0
            for group in groups:
                room = MAX_ROWS - count
                if room <= 0:
                    break
                rows = group['rows'][:room]
                count += len(rows)
                capped.append({'model_label': group['model_label'], 'rows': rows})
            groups = capped
        return {
            'today': today,
            'groups': groups,
            'count': count,
            'truncated': truncated,
        }

    @api.model
    def _activity_digest_model_label(self, res_model):
        """Translated label of a document model, e.g. 'Sales Order'."""
        model = self.env['ir.model']._get(res_model)
        return model.display_name or res_model

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------
    @api.model
    def _activity_digest_mail_values(self, user, data):
        """mail.mail values for one recipient. Built in the recipient's language
        (this recordset already carries their lang in the context)."""
        cell = 'padding:6px 8px;border-bottom:1px solid #e9ecef;vertical-align:top;'
        chunks = []
        for group in data['groups']:
            chunks.append(
                '<h3 style="font-size:14px;margin:18px 0 4px 0;color:#495057;">'
                '%s</h3>' % html_escape(group['model_label']))
            chunks.append('<table width="100%" cellpadding="0" cellspacing="0" '
                          'style="border-collapse:collapse;">')
            for row in group['rows']:
                due = format_date(self.env, row['deadline'], lang_code=user.lang)
                if row['overdue']:
                    when = '<span style="color:#d9534f;font-weight:bold;">%s</span>' % (
                        html_escape(_('Overdue - %s') % due))
                else:
                    when = html_escape(_('Due today - %s') % due)
                detail = row['activity_type']
                if row['summary']:
                    detail = '%s: %s' % (detail, row['summary'])
                chunks.append(
                    '<tr>'
                    '<td style="%(cell)s white-space:nowrap;">%(when)s</td>'
                    '<td style="%(cell)s"><a href="%(url)s" '
                    'style="color:#0d6efd;text-decoration:none;">%(name)s</a>'
                    '<br/><span style="color:#6c757d;">%(detail)s</span></td>'
                    '</tr>' % {
                        'cell': cell,
                        'when': when,
                        'url': html_escape(row['url']),
                        'name': html_escape(row['name']),
                        'detail': html_escape(detail),
                    })
            chunks.append('</table>')
        if data['truncated']:
            chunks.append(
                '<p style="color:#6c757d;">%s</p>' % html_escape(
                    _('Only the first %s activities are listed. Open Odoo to see '
                      'the rest.') % MAX_ROWS))
        body = (
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;'
            'color:#212529;">'
            '<p>%(hello)s</p><p>%(intro)s</p>%(body)s'
            '<p style="color:#6c757d;font-size:12px;margin-top:24px;">%(foot)s</p>'
            '</div>' % {
                'hello': html_escape(_('Hello %s,') % (user.name or '')),
                'intro': html_escape(_(
                    'Activities due today or overdue: %s') % data['count']),
                'body': ''.join(chunks),
                'foot': html_escape(_(
                    'You receive this because "Daily Activity Digest" is enabled '
                    'in your Odoo preferences. Untick it there to stop these '
                    'emails.')),
            })
        values = {
            'subject': _('Your activities for %s') % format_date(
                self.env, data['today'], lang_code=user.lang),
            'email_to': user.email_formatted or user.email,
            'body_html': body,
            'auto_delete': True,
        }
        # OdooBot (the cron user) usually has no address of its own
        email_from = (user.company_id.partner_id.email_formatted
                      or self.env.company.partner_id.email_formatted)
        if email_from:
            values['email_from'] = email_from
        return values

    # ------------------------------------------------------------------
    # sending
    # ------------------------------------------------------------------
    @api.model
    def _activity_digest_send_one(self, user):
        """Build and send one user's digest. Returns the mail.mail, or False
        when that user has nothing due - an empty digest is never sent."""
        digest = self.with_context(lang=user.lang or 'en_US')
        data = digest._activity_digest_collect(user)
        if not data:
            return False
        values = digest._activity_digest_mail_values(user, data)
        if not values.get('email_to'):
            return False
        mail = self.env['mail.mail'].sudo().create(values)
        # force send: a stuck outgoing queue must not swallow a daily digest
        mail.send(raise_exception=False)
        return mail

    @api.model
    def _activity_digest_recipients(self):
        return self.sudo().search([
            ('activity_digest_optin', '=', True),
            ('active', '=', True),
            ('share', '=', False),
        ]).filtered(lambda u: u.email)

    @api.model
    def _activity_digest_cron(self):
        """Daily entry point. Returns the ids of the users who were emailed."""
        if not (self.env.su or self.env.user.has_group('base.group_system')):
            raise AccessError(_('Only administrators can run the activity digest.'))
        if not self._activity_digest_enabled():
            _logger.info('Activity digest is switched off globally; nothing sent.')
            return []
        sent = []
        for user in self._activity_digest_recipients():
            # one bad recipient must never cost the others their digest
            try:
                with self.env.cr.savepoint():
                    if self._activity_digest_send_one(user):
                        sent.append(user.id)
            except Exception:  # noqa: BLE001 - logged and skipped, run continues
                _logger.exception('Activity digest failed for user %s (id %s).',
                                  user.login, user.id)
        _logger.info('Activity digest: %s email(s) sent.', len(sent))
        return sent
