# -*- coding: utf-8 -*-
# Part of access_rights_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import api, fields, models, tools

# Effective rights of a GROUP over every model it can reach.
#
# Unlike the matrix, this view resolves inheritance. A member of a group also
# belongs to every group that group implies (res.groups.implied_ids), and Odoo
# grants the union of their access control lines; on top of that, a line with no
# group at all is granted to every user (ir.model.access._get_allowed_models
# accepts "a.group_id IS NULL OR a.group_id IN <user groups>").
#
# The recursive term walks implied_ids transitively. UNION - not UNION ALL -
# de-duplicates, so a cycle in the implication graph terminates instead of
# looping forever. Each row records whether the rights come from the group's own
# lines (via_direct), from an implied group (via_inherited) or from a global line
# (via_global), and which groups supplied them.
#
# As in the matrix, the id is derived from the pair (group x 1000000 + model, in
# bigint) so that it stays stable when access lines change elsewhere. It assumes
# fewer than 1,000,000 ir.model rows; the product is a bigint and may exceed the
# int4 range, which the ORM never narrows - but nothing outside this report
# should be built on these ids.
#
# Note the shape of this view: one row per group per reachable model. On a
# database with many apps installed that is tens of thousands of rows, and a
# database view carries no indexes, so every search recomputes it. That is
# acceptable for an audit screen, and it is stated on the store listing.
GROUP_VIEW_SQL = """
    WITH RECURSIVE implied AS (
            SELECT g.id AS group_id, g.id AS source_id
              FROM res_groups g
        UNION
            SELECT i.group_id, rel.hid
              FROM implied i
              JOIN res_groups_implied_rel rel ON rel.gid = i.source_id
    ),
    grants AS (
        SELECT i.group_id                        AS group_id,
               a.model_id                        AS model_id,
               a.perm_read                       AS perm_read,
               a.perm_write                      AS perm_write,
               a.perm_create                     AS perm_create,
               a.perm_unlink                     AS perm_unlink,
               (i.source_id = i.group_id)        AS via_direct,
               (i.source_id <> i.group_id)       AS via_inherited,
               FALSE                             AS via_global,
               CASE WHEN i.source_id <> i.group_id
                    THEN i.source_id END         AS source_id
          FROM implied i
          JOIN ir_model_access a ON a.group_id = i.source_id AND a.active
        UNION ALL
        SELECT g.id, a.model_id,
               a.perm_read, a.perm_write, a.perm_create, a.perm_unlink,
               FALSE, FALSE, TRUE, NULL::integer
          FROM res_groups g
    CROSS JOIN ir_model_access a
         WHERE a.group_id IS NULL
           AND a.active
    ),
    effective AS (
        SELECT gr.group_id                      AS group_id,
               gr.model_id                      AS model_id,
               m.model                          AS model_name,
               m.transient                      AS is_wizard,
               BOOL_OR(gr.perm_read)            AS perm_read,
               BOOL_OR(gr.perm_write)           AS perm_write,
               BOOL_OR(gr.perm_create)          AS perm_create,
               BOOL_OR(gr.perm_unlink)          AS perm_unlink,
               BOOL_OR(gr.via_direct)           AS via_direct,
               BOOL_OR(gr.via_inherited)        AS via_inherited,
               BOOL_OR(gr.via_global)           AS via_global,
               STRING_AGG(DISTINCT CAST(gr.source_id AS text), ',')
                                                AS source_group_ids_text
          FROM grants gr
          JOIN ir_model m ON m.id = gr.model_id
      GROUP BY gr.group_id, gr.model_id, m.model, m.transient
    )
    SELECT CAST(e.group_id AS bigint) * 1000000 + e.model_id AS id,
           e.group_id, e.model_id, e.model_name, e.is_wizard,
           e.perm_read, e.perm_write, e.perm_create, e.perm_unlink,
           e.via_direct, e.via_inherited, e.via_global, e.source_group_ids_text,
           CAST(e.perm_read::integer + e.perm_write::integer
                + e.perm_create::integer + e.perm_unlink::integer AS integer) AS perm_count,
           (CASE WHEN e.perm_read   THEN 'R' ELSE '-' END ||
            CASE WHEN e.perm_write  THEN 'W' ELSE '-' END ||
            CASE WHEN e.perm_create THEN 'C' ELSE '-' END ||
            CASE WHEN e.perm_unlink THEN 'D' ELSE '-' END)  AS rights_code
      FROM effective e
"""


class AccessRightsGroup(models.Model):
    _name = 'access.rights.group'
    _description = 'Effective Access Rights by Group'
    _auto = False
    _rec_name = 'model_name'
    _order = 'group_id, model_name'

    group_id = fields.Many2one(
        'res.groups', string='Group', readonly=True,
        help='The group whose effective rights this line describes.',
    )
    model_id = fields.Many2one(
        'ir.model', string='Model', readonly=True,
        help='A model the members of this group can reach.',
    )
    model_name = fields.Char(
        string='Technical Model', readonly=True,
        help='Technical name of the model, for example res.partner.',
    )
    is_wizard = fields.Boolean(
        string='Wizard', readonly=True,
        help='Ticked for transient models (wizards).',
    )
    perm_read = fields.Boolean(string='Read', readonly=True)
    perm_write = fields.Boolean(string='Write', readonly=True)
    perm_create = fields.Boolean(string='Create', readonly=True)
    perm_unlink = fields.Boolean(string='Delete', readonly=True)
    perm_count = fields.Integer(
        string='Permissions', readonly=True, group_operator=False,
        help='How many of the four permissions are granted, from 0 to 4.',
    )
    rights_code = fields.Char(
        string='Rights', readonly=True,
        help='Compact form of the four ticks, for example RW-- or RWCD.',
    )
    via_direct = fields.Boolean(
        string='Direct', readonly=True,
        help='Ticked when an access control line is attached to this very group.',
    )
    via_inherited = fields.Boolean(
        string='Inherited', readonly=True,
        help='Ticked when the rights come, wholly or partly, from a group this '
             'group implies.',
    )
    via_global = fields.Boolean(
        string='Global', readonly=True,
        help='Ticked when the rights come, wholly or partly, from an access '
             'control line that carries no group and is therefore granted to '
             'every user.',
    )
    source_group_ids_text = fields.Char(
        string='Inherited From (technical)', readonly=True,
        help='Comma separated ids of the implied groups that grant rights here. '
             'Technical column behind the "Inherited From" field.',
    )
    source_group_ids = fields.Many2many(
        'res.groups', string='Inherited From', compute='_compute_source_group_ids',
        help='The implied groups that supply these rights. Empty when the group '
             'holds the access control lines itself.',
    )

    @api.depends('source_group_ids_text')
    def _compute_source_group_ids(self):
        # One query for the whole recordset: read the ids out of the aggregated
        # column, then resolve them in a single browse.
        per_line = {}
        wanted = set()
        for line in self:
            ids = [int(part) for part in (line.source_group_ids_text or '').split(',') if part]
            per_line[line] = ids
            wanted.update(ids)
        alive = set(self.env['res.groups'].browse(sorted(wanted)).exists().ids)
        groups = self.env['res.groups']
        for line in self:
            # sorted numerically: the aggregated column is text, so 10 would
            # otherwise come before 9 in the tag list
            line.source_group_ids = groups.browse(
                sorted(i for i in per_line[line] if i in alive))

    def _view_sql(self):
        """SQL of the read-only view. Split out so the statement built in
        init() only ever interpolates ``self._`` members."""
        return GROUP_VIEW_SQL

    def init(self):
        # Read-only database view. The module never writes to ir.model.access or
        # res.groups: the only value interpolated into the statement is
        # self._table, which comes from _name, and no user input reaches it.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('CREATE VIEW %s AS (%s)' % (self._table, self._view_sql()))
