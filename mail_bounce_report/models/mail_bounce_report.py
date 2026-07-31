# -*- coding: utf-8 -*-
# Part of mail_bounce_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import re

from odoo import _, fields, models, tools
from odoo.exceptions import UserError

# A table name coming out of the registry must be a bare SQL identifier before
# it is ever interpolated into a CREATE VIEW statement.
IDENTIFIER_RE = re.compile(r'^[a-z_][a-z0-9_]*$')

# The threshold is read straight out of ir_config_parameter, where anybody with
# access to Technical / System Parameters can type anything at all. It is
# accepted only as 1 to 9 ASCII digits, which keeps it inside PostgreSQL's
# integer range: an unbounded cast of e.g. "99999999999" raises "value out of
# range for type integer" on EVERY read and takes the whole report down. The
# same expression is used in SQL and in Python so the Settings page can never
# display a different threshold from the one the report applies - note that
# str.isdigit() would NOT do, as it accepts non-ASCII digits the SQL side
# rejects.
THRESHOLD_RE = re.compile(r'^[0-9]{1,9}$')
THRESHOLD_SQL_RE = '^\\s*[0-9]{1,9}\\s*$'
MAX_THRESHOLD = 999999999

# Odoo's own mail code treats 10 bounces as the point where an address is dead:
# discuss.channel.MAX_BOUNCE_LIMIT is 10 on every series from 14.0 to 19.0 and a
# partner reaching it is unfollowed from the channel. The report uses the same
# number as its default so the flag means the same thing as core's own limit.
DEFAULT_THRESHOLD = 10
PARAM_THRESHOLD = 'mail_bounce_report.bounce_threshold'

# res.partner.message_bounce (the mail.thread.blacklist mixin) is the only bounce
# counter Odoo keeps per contact. mail.notification rows carry the per-message
# bounce status but the model is declared with _log_access = False on every
# supported series, so there is NO timestamp on the bounce itself. The nearest
# honest date is the date of the message that bounced (mail_message.date), which
# is what last_bounce_message_date reports - it is deliberately not presented as
# "the moment the bounce arrived", because Odoo never stores that.
REPORT_VIEW_SQL = """
    WITH configured_threshold AS (
        SELECT COALESCE((
            SELECT CASE WHEN value ~ '{threshold_re}' THEN btrim(value)::integer END
              FROM ir_config_parameter
             WHERE key = '{param}'
             LIMIT 1
        ), {default}) AS threshold
    ),
    bounced_notifications AS (
        SELECT n.res_partner_id  AS partner_id,
               COUNT(*)          AS bounced_message_count,
               MAX(msg.date)     AS last_bounce_message_date
          FROM {notification_table} n
          JOIN mail_message msg ON msg.id = n.mail_message_id
         WHERE n.notification_status = 'bounce'
           AND n.res_partner_id IS NOT NULL
      GROUP BY n.res_partner_id
    )
    SELECT p.id                                          AS id,
           p.id                                          AS partner_id,
           p.name                                        AS partner_name,
           p.email                                       AS email,
           p.email_normalized                            AS email_normalized,
           (p.email_normalized IS NOT NULL)              AS has_email,
           COALESCE(p.message_bounce, 0)                 AS bounce_count,
           t.threshold                                   AS bounce_threshold,
           (COALESCE(p.message_bounce, 0) >= t.threshold) AS above_threshold,
           COALESCE(b.bounced_message_count, 0)          AS bounced_message_count,
           b.last_bounce_message_date                    AS last_bounce_message_date,
           (bl.id IS NOT NULL)                           AS blacklisted,
           bl.id                                         AS blacklist_id,
           bl.create_date                                AS blacklist_date,
           p.company_id                                  AS company_id,
           p.country_id                                  AS country_id,
           p.active                                      AS partner_active,
           COALESCE(p.partner_share, FALSE)              AS partner_share,
           p.type                                        AS partner_type
      FROM res_partner p
      CROSS JOIN configured_threshold t
      LEFT JOIN bounced_notifications b ON b.partner_id = p.id
      LEFT JOIN mail_blacklist bl
             ON bl.email = p.email_normalized
            AND COALESCE(bl.active, FALSE)
     WHERE COALESCE(p.message_bounce, 0) > 0
        OR bl.id IS NOT NULL
"""


class MailBounceReport(models.Model):
    """Read-only view over the bounce counters Odoo already keeps on contacts.

    The module owns no table of its own and never writes to res.partner,
    mail.blacklist or mail.notification: every column below is selected out of
    core data by the database view built in :meth:`init`.
    """
    _name = 'mail.bounce.report'
    _description = 'Email Bounce Report'
    _auto = False
    _rec_name = 'partner_name'
    _order = 'bounce_count desc, partner_name, id'

    partner_id = fields.Many2one(
        'res.partner', string='Contact', readonly=True,
        help='The contact this line reports on. Open it to see the address in context.',
    )
    partner_name = fields.Char(string='Name', readonly=True)
    email = fields.Char(
        string='Email', readonly=True,
        help='The email address as stored on the contact.',
    )
    email_normalized = fields.Char(
        string='Normalized Email', readonly=True,
        help='Lower-cased address without the display name, as Odoo computes it. '
             'This is the value matched against the blacklist.',
    )
    has_email = fields.Boolean(
        string='Has Email', readonly=True,
        help='Unticked when the contact carries no usable email address. Such a '
             'contact can still hold a bounce counter from an address that was '
             'later cleared, and can never match a blacklist entry.',
    )
    bounce_count = fields.Integer(
        string='Bounces', readonly=True, group_operator=False,
        help='Value of the standard res.partner "Bounce" counter '
             '(message_bounce). Odoo increments it when a bounce is received '
             'for this address and resets it to zero when the address answers.',
    )
    bounce_threshold = fields.Integer(
        string='Threshold', readonly=True, group_operator=False,
        help='The threshold currently configured in Settings. Identical on '
             'every line - it is shown so the "Above Threshold" flag can be read '
             'without leaving the report.',
    )
    above_threshold = fields.Boolean(
        string='Above Threshold', readonly=True,
        help='Ticked when Bounces is greater than OR EQUAL TO the configured '
             'threshold. The comparison is inclusive, matching the >= test Odoo '
             'itself uses against its MAX_BOUNCE_LIMIT.',
    )
    bounced_message_count = fields.Integer(
        string='Bounced Messages', readonly=True,
        help='Number of individual messages to this contact that are still '
             'recorded as bounced. It can be lower than the Bounce counter: '
             'notifications are garbage-collected, and the counter is shared by '
             'every record carrying the same address.',
    )
    last_bounce_message_date = fields.Datetime(
        string='Last Bounced Message', readonly=True,
        help='Date of the most recent message to this contact that is recorded '
             'as bounced. Odoo stores no timestamp for the bounce itself, so '
             'this is the date of the message that bounced, not the moment the '
             'bounce came back. Empty when no bounced message survives.',
    )
    blacklisted = fields.Boolean(
        string='Blacklisted', readonly=True,
        help='Ticked when the normalized address matches an active mail.blacklist entry.',
    )
    blacklist_id = fields.Many2one(
        'mail.blacklist', string='Blacklist Entry', readonly=True,
        help='The active blacklist entry for this address, if any.',
    )
    blacklist_date = fields.Datetime(
        string='Blacklisted On', readonly=True,
        help='When the blacklist entry for this address was created.',
    )
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    country_id = fields.Many2one('res.country', string='Country', readonly=True)
    partner_active = fields.Boolean(
        string='Active Contact', readonly=True,
        help='Unticked for archived contacts, which the report still lists.',
    )
    # Selected only so the record rules shipped in security/ can mirror the ones
    # core puts on res.partner exactly instead of approximating them.
    partner_share = fields.Boolean(string='Share Contact', readonly=True)
    partner_type = fields.Char(
        string='Address Type', readonly=True,
        help='Value of res.partner.type. Selected so that the private-address '
             'rules core ships on 14.0-16.0 can be mirrored on this report; on '
             '17.0 and later the "private" address type no longer exists.',
    )

    def _report_query(self):
        """Return the SELECT backing this report, resolved for the running series.

        The only interpolated values are literals owned by this module and
        mail.notification's table name, which comes from the registry (14.0
        still calls it mail_message_res_partner_needaction_rel). It is asserted
        to be a bare SQL identifier before use. No user input reaches this SQL:
        the configured threshold is read inside the query and cast only after a
        digits-only regex check, so a hand-edited parameter can neither inject
        nor crash it.
        """
        notification_table = self.env['mail.notification']._table
        if not IDENTIFIER_RE.match(notification_table):
            raise ValueError(
                'Unexpected mail.notification table name %r' % notification_table)
        return REPORT_VIEW_SQL.format(
            param=PARAM_THRESHOLD,
            default=DEFAULT_THRESHOLD,
            threshold_re=THRESHOLD_SQL_RE,
            notification_table=notification_table,
        )

    def init(self):
        """(Re)build the read-only database view backing this report."""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            'CREATE VIEW %s AS (%s)' % (self._table, self._report_query()))

    def _bounce_threshold(self):
        """Return the configured threshold, using the same rules as the SQL view.

        ``get_param`` cannot be trusted with a plain default here: it returns the
        default for any falsy stored value, so a legitimately configured 0 would
        read back as 10. The raw value is therefore validated explicitly, with
        exactly the pattern the SQL view applies, so the Settings page can never
        show a threshold the report does not use.
        """
        raw = self.env['ir.config_parameter'].sudo().get_param(PARAM_THRESHOLD)
        raw = (raw or '').strip()
        return int(raw) if THRESHOLD_RE.match(raw) else DEFAULT_THRESHOLD

    def action_open_contact(self):
        """Open the contact behind this line. Navigation only - nothing is written."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contact'),
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
        }

    def action_open_blacklist_entry(self):
        """Open the blacklist entry for this address. Navigation only."""
        self.ensure_one()
        if not self.blacklist_id:
            raise UserError(_(
                'This address is not on the email blacklist. This report never '
                'adds addresses to the blacklist; use Technical / Email '
                'Blacklist to do that.'
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Blacklisted Email Address'),
            'res_model': 'mail.blacklist',
            'res_id': self.blacklist_id.id,
            'view_mode': 'form',
        }
