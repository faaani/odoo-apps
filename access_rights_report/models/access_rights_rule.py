# -*- coding: utf-8 -*-
# Part of access_rights_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models, tools

# The record rules (ir.rule) side of the audit: access control lines say which
# models a group may touch, record rules say WHICH RECORDS of those models it
# sees. The report keeps ir_rule.id as its own id, so the many2many below can
# reuse the very relation table ir.rule.groups uses (rule_group_rel) and stay
# searchable, instead of copying group links into a second table.
#
# A rule with no group is global: Odoo applies it to every user and ANDs it with
# the group rules, so a global rule can never be widened by a group rule. That
# distinction is the "Global" tick.
#
# Because the model is _auto = False, Odoo skips the whole schema section of
# _auto_init, so that many2many never reflects a relation or a foreign key of its
# own: core's rule_group_rel keeps exactly the constraints ir.rule gave it. The
# field is still writable at ORM level, though - the read-only access line in
# security/ir.model.access.csv is the one thing that stops a write reaching that
# core table. Never grant write on this model.
RULE_VIEW_SQL = """
    SELECT r.id                        AS id,
           r.id                        AS rule_id,
           r.name                      AS rule_name,
           r.model_id                  AS model_id,
           m.model                     AS model_name,
           m.transient                 AS is_wizard,
           r.domain_force              AS domain_force,
           r."global"                  AS is_global,
           r.active                    AS rule_active,
           r.perm_read                 AS perm_read,
           r.perm_write                AS perm_write,
           r.perm_create               AS perm_create,
           r.perm_unlink               AS perm_unlink,
           CAST((SELECT COUNT(*)
                   FROM rule_group_rel rg
                  WHERE rg.rule_group_id = r.id) AS integer)   AS group_count,
           CAST(r.perm_read::integer + r.perm_write::integer
                + r.perm_create::integer + r.perm_unlink::integer AS integer) AS perm_count,
           (CASE WHEN r.perm_read   THEN 'R' ELSE '-' END ||
            CASE WHEN r.perm_write  THEN 'W' ELSE '-' END ||
            CASE WHEN r.perm_create THEN 'C' ELSE '-' END ||
            CASE WHEN r.perm_unlink THEN 'D' ELSE '-' END)     AS rights_code
      FROM ir_rule r
      JOIN ir_model m ON m.id = r.model_id
"""


class AccessRightsRule(models.Model):
    _name = 'access.rights.rule'
    _description = 'Record Rules Report'
    _auto = False
    _rec_name = 'rule_name'
    _order = 'model_name, rule_name'

    rule_id = fields.Many2one(
        'ir.rule', string='Record Rule', readonly=True,
        help='The ir.rule record this line reports on.',
    )
    rule_name = fields.Char(
        string='Rule', readonly=True,
        help='Name of the record rule.',
    )
    model_id = fields.Many2one(
        'ir.model', string='Model', readonly=True,
        help='The model whose records the rule filters.',
    )
    model_name = fields.Char(
        string='Technical Model', readonly=True,
        help='Technical name of the model, for example res.partner.',
    )
    is_wizard = fields.Boolean(
        string='Wizard', readonly=True,
        help='Ticked for transient models (wizards).',
    )
    domain_force = fields.Text(
        string='Domain', readonly=True,
        help='The domain the rule forces on every query. Records outside it are '
             'invisible to the users the rule applies to.',
    )
    is_global = fields.Boolean(
        string='Global', readonly=True,
        help='Ticked when the rule carries no group. A global rule applies to '
             'every user and is combined with AND, so no group rule can widen it.',
    )
    rule_active = fields.Boolean(
        string='Active', readonly=True,
        help='Unticked rules are disabled and enforce nothing.',
    )
    group_ids = fields.Many2many(
        'res.groups', 'rule_group_rel', 'rule_group_id', 'group_id',
        string='Groups', readonly=True,
        help='Groups the rule applies to. Group rules are combined with OR: a '
             'user in several of them sees the union of their domains.',
    )
    group_count = fields.Integer(
        string='# Groups', readonly=True, aggregator=False,
        help='How many groups the rule is attached to. Zero means it is global.',
    )
    perm_read = fields.Boolean(
        string='Read', readonly=True, help='The rule filters read access.')
    perm_write = fields.Boolean(
        string='Write', readonly=True, help='The rule filters write access.')
    perm_create = fields.Boolean(
        string='Create', readonly=True, help='The rule filters record creation.')
    perm_unlink = fields.Boolean(
        string='Delete', readonly=True, help='The rule filters deletion.')
    perm_count = fields.Integer(
        string='Operations', readonly=True, aggregator=False,
        help='How many of the four operations the rule applies to, from 0 to 4.',
    )
    rights_code = fields.Char(
        string='Applies To', readonly=True,
        help='Compact form of the four operations, for example R--- or RWCD.',
    )

    def _view_sql(self):
        """SQL of the read-only view. Split out so the statement built in
        init() only ever interpolates ``self._`` members."""
        return RULE_VIEW_SQL

    def init(self):
        # Read-only database view. The module never writes to ir.rule: the only
        # value interpolated into the statement is self._table, which comes from
        # _name, and no user input reaches this SQL.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('CREATE VIEW %s AS (%s)' % (self._table, self._view_sql()))
