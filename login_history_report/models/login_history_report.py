# -*- coding: utf-8 -*-
# Part of login_history_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import SUPERUSER_ID, fields, models, tools

# res.users.login_date is a RELATED, non-stored field over log_ids.create_date:
# a domain on it matches ANY login row of the user, never "the latest one", and
# it cannot be sorted on. This report therefore aggregates res_users_log once
# (MAX(create_date) per user) inside a database view, so last login, days since
# last login and the never-logged flag are real, searchable, sortable columns.
REPORT_VIEW_SQL = """
    SELECT u.id                                            AS id,
           u.id                                            AS user_id,
           u.login                                         AS login,
           p.name                                          AS user_name,
           u.company_id                                    AS company_id,
           u.active                                        AS user_active,
           COALESCE(u.share, FALSE)                        AS share,
           CASE WHEN COALESCE(u.share, FALSE)
                THEN 'portal' ELSE 'internal' END          AS user_type,
           u.create_date                                   AS user_create_date,
           l.last_login                                    AS last_login,
           (l.last_login IS NULL)                          AS never_logged,
           COALESCE(l.last_login, u.create_date,
                    now() AT TIME ZONE 'UTC')              AS reference_date,
           GREATEST(0, EXTRACT(DAY FROM ((now() AT TIME ZONE 'UTC')
                - COALESCE(l.last_login, u.create_date,
                           now() AT TIME ZONE 'UTC')))::integer) AS days_since_login,
           CASE
               WHEN l.last_login IS NULL THEN 'never'
               WHEN (now() AT TIME ZONE 'UTC') - l.last_login < interval '30 days' THEN 'recent'
               WHEN (now() AT TIME ZONE 'UTC') - l.last_login < interval '90 days' THEN 'idle'
               ELSE 'dormant'
           END                                             AS activity_status
      FROM res_users u
      JOIN res_partner p ON p.id = u.partner_id
      LEFT JOIN (
             SELECT create_uid,
                    MAX(create_date) AS last_login
               FROM res_users_log
              WHERE create_uid IS NOT NULL
           GROUP BY create_uid
           ) l ON l.create_uid = u.id
     WHERE u.id != %(superuser_id)s
"""


class LoginHistoryReport(models.Model):
    _name = 'login.history.report'
    _description = 'User Login Report'
    _auto = False
    _rec_name = 'user_name'
    _order = 'days_since_login desc, login'

    user_id = fields.Many2one(
        'res.users', string='User', readonly=True,
        help='The user account this line reports on.',
    )
    user_name = fields.Char(string='Name', readonly=True)
    login = fields.Char(string='Login', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    # Same relation table as res.users.company_ids, so the record rule shipped in
    # security/ can mirror base.res_users_rule exactly instead of approximating it.
    company_ids = fields.Many2many(
        'res.company', 'res_company_users_rel', 'user_id', 'cid',
        string='Allowed Companies', readonly=True,
    )
    user_active = fields.Boolean(
        string='Enabled', readonly=True,
        help='Unticked for archived (deactivated) user accounts.',
    )
    share = fields.Boolean(
        string='Portal / Public', readonly=True,
        help='Ticked for portal and public users, who do not consume an internal seat.',
    )
    user_type = fields.Selection(
        [('internal', 'Internal User'), ('portal', 'Portal / Public User')],
        string='User Type', readonly=True,
    )
    user_create_date = fields.Datetime(
        string='Account Created', readonly=True,
        help='When the user account was created.',
    )
    last_login = fields.Datetime(
        string='Last Login', readonly=True,
        help='Date of the most recent login record for this user. '
             'Empty when the account has never been used to log in.',
    )
    never_logged = fields.Boolean(
        string='Never Logged In', readonly=True,
        help='Ticked when no login record exists at all for this account.',
    )
    reference_date = fields.Datetime(
        string='Reference Date', readonly=True,
        help='Date the "Days Since Last Login" figure is counted from: the last '
             'login, or the account creation date when the user never logged in.',
    )
    days_since_login = fields.Integer(
        string='Days Since Last Login', readonly=True, aggregator=False,
        help='Whole days between the reference date and now. For accounts that '
             'never logged in this is the age of the account.',
    )
    activity_status = fields.Selection(
        [
            ('never', 'Never Logged In'),
            ('recent', 'Active (last 30 days)'),
            ('idle', 'Idle (30-90 days)'),
            ('dormant', 'Dormant (90+ days)'),
        ],
        string='Login Status', readonly=True,
    )

    def init(self):
        # Read-only database view: the module never writes to res.users.
        # The only interpolated value is self._table (derived from _name); the
        # %(superuser_id)s placeholder is left untouched by that interpolation
        # and is bound by psycopg2 below. No user input reaches this SQL.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            'CREATE VIEW %s AS (%s)' % (self._table, REPORT_VIEW_SQL),
            {'superuser_id': SUPERUSER_ID},
        )
