# -*- coding: utf-8 -*-
# Part of user_group_audit_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import SUPERUSER_ID, fields, models, tools

# Answering "who can do what in this database?" from the Users list means opening
# every user one by one. This report answers it in one screen.
#
# Two facts drive the SQL below:
#
# 1. Group membership lives in the many2many table res_groups_users_rel. Odoo
#    14.0-18.0 expand implied groups INTO that table when a user is saved, while
#    19.0 keeps only the groups explicitly assigned and computes the rest at
#    runtime (res.users.all_group_ids). A report that only reads the relation
#    table would therefore under-report privileges on 19.0. Every flag and count
#    here is built from the TRANSITIVE CLOSURE of res.groups.implied_ids, which
#    is the same set on every series. The closure is a single recursive CTE over
#    res_groups (a table with a few hundred rows), not a loop over users.
#
# 2. res.users.login_date is a RELATED, non-stored field over log_ids.create_date:
#    a domain on it matches ANY login row of the user and it cannot be sorted on.
#    The never-logged-in flag is therefore derived from one grouped query over
#    res_users_log (MAX(create_date) per user), joined once.
REPORT_VIEW_SQL = """
    WITH RECURSIVE group_closure AS (
             SELECT g.id AS gid, g.id AS eff_gid
               FROM res_groups g
              UNION
             SELECT c.gid, r.hid
               FROM group_closure c
               JOIN res_groups_implied_rel r ON r.gid = c.eff_gid
         ),
         -- A missing xmlid yields NULL here, `gid = NULL` is NULL, BOOL_OR
         -- skips it and COALESCE turns it into FALSE: the report degrades to
         -- "no such group" instead of failing. Deliberate - do not turn the
         -- join below into an INNER JOIN.
         key_groups AS (
             SELECT MAX(CASE WHEN d.name = 'group_system' THEN d.res_id END)      AS g_system,
                    MAX(CASE WHEN d.name = 'group_erp_manager' THEN d.res_id END) AS g_erp,
                    MAX(CASE WHEN d.name = 'group_user' THEN d.res_id END)        AS g_user,
                    MAX(CASE WHEN d.name = 'group_portal' THEN d.res_id END)      AS g_portal,
                    MAX(CASE WHEN d.name = 'group_public' THEN d.res_id END)      AS g_public
               FROM ir_model_data d
              WHERE d.module = 'base'
                AND d.model = 'res.groups'
                AND d.name IN ('group_system', 'group_erp_manager', 'group_user',
                               'group_portal', 'group_public')
         ),
         assigned_stats AS (
             SELECT ur.uid AS uid, COUNT(DISTINCT ur.gid) AS assigned_count
               FROM res_groups_users_rel ur
           GROUP BY ur.uid
         ),
         effective AS (
             SELECT DISTINCT ur.uid AS uid, c.eff_gid AS gid
               FROM res_groups_users_rel ur
               JOIN group_closure c ON c.gid = ur.gid
         ),
         effective_stats AS (
             SELECT e.uid                                       AS uid,
                    COUNT(*)                                    AS effective_count,
                    BOOL_OR(e.gid = k.g_system)                 AS is_settings_admin,
                    BOOL_OR(e.gid = k.g_erp)                    AS is_access_rights_admin,
                    BOOL_OR(e.gid = k.g_user)                   AS in_internal_group,
                    BOOL_OR(e.gid = k.g_portal)                 AS in_portal_group,
                    BOOL_OR(e.gid = k.g_public)                 AS in_public_group
               FROM effective e
               CROSS JOIN key_groups k
           GROUP BY e.uid
         ),
         last_login AS (
             SELECT create_uid, MAX(create_date) AS last_login
               FROM res_users_log
              WHERE create_uid IS NOT NULL
           GROUP BY create_uid
         )
    SELECT u.id                                             AS id,
           u.id                                             AS user_id,
           u.login                                          AS login,
           p.name                                           AS user_name,
           u.company_id                                     AS company_id,
           u.active                                         AS user_active,
           (NOT u.active)                                   AS is_archived,
           COALESCE(u.share, FALSE)                         AS share,
           u.create_date                                    AS user_create_date,
           l.last_login                                     AS last_login,
           (l.last_login IS NULL)                           AS never_logged_in,
           COALESCE(a.assigned_count, 0)                    AS assigned_group_count,
           COALESCE(e.effective_count, 0)                   AS effective_group_count,
           GREATEST(COALESCE(e.effective_count, 0)
                    - COALESCE(a.assigned_count, 0), 0)     AS implied_group_count,
           COALESCE(e.is_settings_admin, FALSE)             AS is_settings_admin,
           COALESCE(e.is_access_rights_admin, FALSE)        AS is_access_rights_admin,
           (COALESCE(e.is_settings_admin, FALSE)
            OR COALESCE(e.is_access_rights_admin, FALSE))   AS has_system_access,
           CASE
               WHEN COALESCE(e.is_settings_admin, FALSE) THEN 'settings'
               WHEN COALESCE(e.is_access_rights_admin, FALSE) THEN 'access_rights'
               ELSE 'standard'
           END                                              AS access_level,
           CASE
               WHEN COALESCE(e.in_internal_group, FALSE) THEN 'internal'
               WHEN COALESCE(e.in_portal_group, FALSE) THEN 'portal'
               WHEN COALESCE(e.in_public_group, FALSE) THEN 'public'
               ELSE 'none'
           END                                              AS user_type
      FROM res_users u
      JOIN res_partner p ON p.id = u.partner_id
      LEFT JOIN assigned_stats a ON a.uid = u.id
      LEFT JOIN effective_stats e ON e.uid = u.id
      LEFT JOIN last_login l ON l.create_uid = u.id
     WHERE u.id != %(superuser_id)s
"""


class UserGroupAuditReport(models.Model):
    _name = 'user.group.audit.report'
    _description = 'User Access Audit Report'
    _auto = False
    _rec_name = 'user_name'
    # Ordering on a computed flag forces the effective-group CTE to be
    # evaluated for every row before the LIMIT; the name is indexed-friendly
    # and administrators are highlighted by the list decoration anyway.
    _order = 'user_name'

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
    # Reuses the standard membership table, so this is exactly what the Groups
    # page of the user form shows - no copy of the data is kept anywhere.
    group_ids = fields.Many2many(
        'res.groups', 'res_groups_users_rel', 'uid', 'gid',
        string='Assigned Groups', readonly=True,
        help='Groups recorded on the user account. On Odoo 14.0-18.0 Odoo writes '
             'implied groups into this list when the user is saved, so there it is '
             'already the effective set; on Odoo 19.0 it holds the directly '
             'assigned groups only. The flags and counts on this report always use '
             'the effective set (assigned groups plus everything they imply).',
    )
    user_active = fields.Boolean(
        string='Enabled', readonly=True,
        help='Unticked for archived (deactivated) user accounts.',
    )
    is_archived = fields.Boolean(
        string='Archived', readonly=True,
        help='Ticked when the user account is archived. An archived account cannot '
             'log in, but it keeps every group it was granted.',
    )
    share = fields.Boolean(
        string='Portal / Public', readonly=True,
        help='Ticked for portal and public users, who do not consume an internal seat.',
    )
    user_type = fields.Selection(
        [
            ('internal', 'Internal User'),
            ('portal', 'Portal User'),
            ('public', 'Public User'),
            ('none', 'No User Type Group'),
        ],
        string='User Type', readonly=True,
        help='Derived from the effective groups: Internal User (base.group_user), '
             'Portal User (base.group_portal), Public User (base.group_public). '
             '"No User Type Group" means the account holds none of the three - '
             'usually an integration/API account, worth a second look in an audit.',
    )
    has_system_access = fields.Boolean(
        string='System Access', readonly=True,
        help='Ticked when the effective groups include Administration / Settings '
             '(base.group_system) or Administration / Access Rights '
             '(base.group_erp_manager). These users can change access rights.',
    )
    is_settings_admin = fields.Boolean(
        string='Settings Admin', readonly=True,
        help='Effective member of Administration / Settings (base.group_system).',
    )
    is_access_rights_admin = fields.Boolean(
        string='Access Rights Admin', readonly=True,
        help='Effective member of Administration / Access Rights '
             '(base.group_erp_manager).',
    )
    access_level = fields.Selection(
        [
            ('settings', 'Settings (full administrator)'),
            ('access_rights', 'Access Rights'),
            ('standard', 'No administration group'),
        ],
        string='Access Level', readonly=True,
        help='Highest administration group held, through the effective groups.',
    )
    assigned_group_count = fields.Integer(
        string='Assigned Group Count', readonly=True, group_operator=False,
        help='Number of groups recorded on the user account.',
    )
    effective_group_count = fields.Integer(
        string='Effective Groups', readonly=True, group_operator=False,
        help='Number of groups the user really holds: the assigned groups plus '
             'every group those imply, transitively.',
    )
    implied_group_count = fields.Integer(
        string='Groups via Implication', readonly=True, group_operator=False,
        help='Effective groups minus assigned groups: access the user holds '
             'without it being ticked on the account. On Odoo 14.0-18.0 this is '
             'normally 0, because Odoo writes implied groups onto the user record, '
             'so anything above 0 is worth a look. On Odoo 19.0, which stores only '
             'the directly assigned groups, a positive number is expected.',
    )
    user_create_date = fields.Datetime(
        string='Account Created', readonly=True,
        help='When the user account was created.',
    )
    last_login = fields.Datetime(
        string='Last Login', readonly=True,
        help='Most recent login record for this account, empty when the account '
             'has never been used to log in.',
    )
    never_logged_in = fields.Boolean(
        string='Never Logged In', readonly=True,
        help='Ticked when no login record exists at all for this account.',
    )

    def init(self):
        # Read-only database view: this module never writes to res.users, to
        # res.groups or to the membership table.
        # The only interpolated value is self._table (derived from _name); the
        # %(superuser_id)s placeholder is left untouched by that interpolation and
        # is bound by psycopg2 below. No user input reaches this SQL.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            'CREATE VIEW %s AS (%s)' % (self._table, REPORT_VIEW_SQL),
            {'superuser_id': SUPERUSER_ID},
        )
