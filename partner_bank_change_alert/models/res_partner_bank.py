# -*- coding: utf-8 -*-
# Part of partner_bank_change_alert. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.tools import html_escape, str2bool

_logger = logging.getLogger(__name__)

PARAM_ENABLED = 'partner_bank_change_alert.enabled'
PARAM_GROUP_ID = 'partner_bank_change_alert.group_id'
# Fields whose change justifies an alert. allow_out_payment (the "Send Money"
# trust switch, base on 16.0+) is the most fraud-critical of them and is
# audited wherever the field exists on this series.
SENSITIVE_FIELDS = ('acc_number', 'partner_id', 'bank_id', 'acc_holder_name',
                    'allow_out_payment')


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------
    @api.model
    def _bank_alert_stored_group_id(self):
        """Return the configured alert group id, or 0 for "use the default".

        Invalid or stale values (unparsable, group deleted) count as unset.
        """
        icp = self.env['ir.config_parameter'].sudo()
        try:
            group_id = int(icp.get_param(PARAM_GROUP_ID) or 0)
        except (TypeError, ValueError):
            group_id = 0
        if group_id and not self.env['res.groups'].sudo().browse(
                group_id).exists():
            group_id = 0
        return group_id

    @api.model
    def _bank_alert_config(self):
        icp = self.env['ir.config_parameter'].sudo()
        # get_param() returns the default for any falsy stored value, so the
        # enabled flag is stored as the strings 'True'/'False' and read back
        # explicitly (a default-True Boolean can never be switched off through
        # a plain config_parameter= binding).
        try:
            enabled = str2bool(icp.get_param(PARAM_ENABLED, 'True'))
        except ValueError:
            enabled = True
        group_id = self._bank_alert_stored_group_id()
        group = self.env['res.groups'].sudo().browse(group_id) if group_id \
            else self._bank_alert_default_group()
        return {'enabled': enabled, 'group': group}

    @api.model
    def _bank_alert_default_group(self):
        # account is deliberately NOT a dependency (res.partner.bank lives in
        # base): resolve its manager group dynamically when it is installed,
        # else fall back to the Settings administrators.
        group = self.env.ref('account.group_account_manager',
                             raise_if_not_found=False)
        return group or self.env.ref('base.group_system',
                                     raise_if_not_found=False)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @api.model
    def _bank_alert_mask(self, number):
        """Mask an account number to its last 4 characters (``****1234``).

        The full number must never appear in an alert message; values of 4
        characters or fewer are masked entirely.
        """
        compact = ''.join((number or '').split())
        if not compact:
            return _('(none)')
        if len(compact) <= 4:
            return '****'
        # the tail is user input and the finished body is wrapped in Markup:
        # escape it like every other interpolated value
        return '****%s' % html_escape(compact[-4:])

    def _bank_alert_describe(self):
        self.ensure_one()
        parts = [self._bank_alert_mask(self.acc_number)]
        if self.bank_id:
            parts.append(_('bank: %s') % html_escape(self.bank_id.name or ''))
        if self.acc_holder_name:
            parts.append(_('holder: %s') % html_escape(self.acc_holder_name))
        return ', '.join(parts)

    @api.model
    def _bank_alert_stamp(self):
        return _('by %(user)s on %(when)s UTC') % {
            'user': html_escape(self.env.user.name or ''),
            'when': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    @api.model
    def _bank_alert_notify_partner_ids(self, group, company=None):
        if not group:
            return []
        # 19.0: user_ids holds only the EXPLICIT members; all_user_ids
        # materializes implied membership, which is what 'users' did on
        # 14.0-18.0 — prefer it when it exists.
        if 'all_user_ids' in group._fields:
            users = group.all_user_ids
        elif 'users' in group._fields:
            users = group.users
        else:
            users = group.user_ids
        if company:
            # never leak (even masked) bank details across companies: only
            # members allowed into the record's company are notified
            users = users.filtered(lambda u: company in u.company_ids)
        return users.partner_id.ids

    def _bank_alert_safe_post(self, partners, body, group, company=None):
        """Post ``body`` on every partner chatter, never raising.

        An anti-fraud audit must not block the business flow, but a silent
        failure would defeat its purpose: each failed post is logged at ERROR
        level and rolled back to its own savepoint so the bank operation
        itself always goes through.
        """
        for partner in partners:
            if not partner or not partner.exists():
                continue
            try:
                with self.env.cr.savepoint():
                    partner.message_post(
                        body=Markup(body),
                        message_type='notification',
                        subtype_xmlid='mail.mt_note',
                        partner_ids=self._bank_alert_notify_partner_ids(
                            group, company=company),
                    )
            except Exception:
                _logger.error(
                    'partner_bank_change_alert: could not post the bank '
                    'account change alert on partner %s; the bank operation '
                    'itself was NOT blocked.', partner.id, exc_info=True)

    # ------------------------------------------------------------------
    # overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super(ResPartnerBank, self).create(vals_list)
        config = self._bank_alert_config()
        if config['enabled']:
            for record in records:
                body = _('Bank account added: %(details)s (%(stamp)s)') % {
                    'details': record._bank_alert_describe(),
                    'stamp': self._bank_alert_stamp(),
                }
                record._bank_alert_safe_post(
                    record.partner_id, body, config['group'],
                    company=record.company_id)
        return records

    def write(self, vals):
        if not any(f in vals for f in SENSITIVE_FIELDS):
            return super(ResPartnerBank, self).write(vals)
        config = self._bank_alert_config()
        if not config['enabled']:
            return super(ResPartnerBank, self).write(vals)
        has_trust_flag = 'allow_out_payment' in self._fields
        previous = {
            record.id: {
                'acc_number': record.acc_number,
                'partner': record.partner_id,
                'bank': record.bank_id,
                'holder': record.acc_holder_name,
                'trusted': record.allow_out_payment if has_trust_flag else None,
            }
            for record in self
        }
        result = super(ResPartnerBank, self).write(vals)
        for record in self:
            old = previous[record.id]
            changes = []
            if old['acc_number'] != record.acc_number:
                changes.append(_('account number %(old)s -> %(new)s') % {
                    'old': self._bank_alert_mask(old['acc_number']),
                    'new': self._bank_alert_mask(record.acc_number),
                })
            if old['bank'] != record.bank_id:
                changes.append(_('bank %(old)s -> %(new)s') % {
                    'old': html_escape(old['bank'].name) if old['bank'] else _('(none)'),
                    'new': html_escape(record.bank_id.name) if record.bank_id else _('(none)'),
                })
            if old['holder'] != record.acc_holder_name:
                changes.append(_('account holder %(old)s -> %(new)s') % {
                    'old': html_escape(old['holder'] or _('(none)')),
                    'new': html_escape(record.acc_holder_name or _('(none)')),
                })
            if has_trust_flag and old['trusted'] != record.allow_out_payment:
                changes.append(
                    _('marked trusted for outgoing payments (Send Money)')
                    if record.allow_out_payment else
                    _('marked untrusted for outgoing payments (Send Money)'))
            moved = old['partner'] != record.partner_id
            if moved:
                changes.append(_('moved from partner %(old)s to %(new)s') % {
                    'old': html_escape(old['partner'].display_name or ''),
                    'new': html_escape(record.partner_id.display_name or ''),
                })
            if not changes:
                continue  # e.g. the same value written again
            body = _('Bank account modified (%(masked)s): %(changes)s (%(stamp)s)') % {
                'masked': self._bank_alert_mask(record.acc_number),
                'changes': '; '.join(changes),
                'stamp': self._bank_alert_stamp(),
            }
            # a repointed account is a red flag for BOTH partners involved
            targets = (old['partner'] | record.partner_id) if moved \
                else record.partner_id
            record._bank_alert_safe_post(targets, body, config['group'],
                                         company=record.company_id)
        return result

    def unlink(self):
        config = self._bank_alert_config()
        pending = []
        if config['enabled']:
            pending = [(record.partner_id, record._bank_alert_describe(),
                        record.company_id)
                       for record in self]
        result = super(ResPartnerBank, self).unlink()
        # post only after the unlink actually succeeded
        for partner, details, company in pending:
            body = _('Bank account removed: %(details)s (%(stamp)s)') % {
                'details': details,
                'stamp': self._bank_alert_stamp(),
            }
            self._bank_alert_safe_post(partner, body, config['group'],
                                       company=company)
        return result
