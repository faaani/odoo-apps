# -*- coding: utf-8 -*-
# Part of access_rights_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError

# One row per model + group, built from ir.model.access.
#
# Odoo allows SEVERAL access control lines for the same model and the same
# group, and grants a permission as soon as ONE active line grants it (see
# ir.model.access._get_allowed_models). The matrix therefore aggregates with
# BOOL_OR instead of listing raw lines, which is what makes it a matrix: exactly
# one row per model/group pair, holding the effective read/write/create/delete
# ticks for that pair.
#
# Two extra shapes of row exist and are flagged:
#  * group_id IS NULL with at least one line  -> a "global" access control line,
#    which Odoo grants to every user whatever their groups (is_global).
#  * no active line at all for the model      -> nobody but the superuser can
#    touch it (no_acl). Kept in the report on purpose: "no line" is an audit
#    finding, not a reason to omit the model.
#
# The id is derived from the pair itself (model x 1000000 + group, in bigint)
# rather than from a window function, so a row keeps the same id when access
# lines are added or removed elsewhere - opening a line from the list would
# otherwise show a different row after any module install. A model that has no
# line at all takes group 0, which no group ever uses, and a model cannot be in
# both shapes at once. The scheme assumes fewer than 1,000,000 res.groups rows;
# the product is a bigint and does exceed the int4 range on a database with many
# models, which the ORM never narrows - but nothing outside this report should be
# built on these ids.
MATRIX_VIEW_SQL = """
    WITH acl AS (
        SELECT a.model_id                  AS model_id,
               a.group_id                  AS group_id,
               BOOL_OR(a.perm_read)        AS perm_read,
               BOOL_OR(a.perm_write)       AS perm_write,
               BOOL_OR(a.perm_create)      AS perm_create,
               BOOL_OR(a.perm_unlink)      AS perm_unlink,
               COUNT(*)                    AS acl_count
          FROM ir_model_access a
         WHERE a.active
      GROUP BY a.model_id, a.group_id
    ),
    matrix_rows AS (
        SELECT m.id            AS model_id,
               m.model         AS model_name,
               m.transient     AS is_wizard,
               acl.group_id    AS group_id,
               FALSE           AS no_acl,
               acl.perm_read   AS perm_read,
               acl.perm_write  AS perm_write,
               acl.perm_create AS perm_create,
               acl.perm_unlink AS perm_unlink,
               acl.acl_count   AS acl_count
          FROM acl
          JOIN ir_model m ON m.id = acl.model_id
        UNION ALL
        SELECT m.id, m.model, m.transient,
               NULL::integer, TRUE,
               FALSE, FALSE, FALSE, FALSE, 0
          FROM ir_model m
         WHERE NOT EXISTS (SELECT 1
                             FROM ir_model_access a
                            WHERE a.model_id = m.id
                              AND a.active)
    )
    SELECT CAST(r.model_id AS bigint) * 1000000
           + COALESCE(r.group_id, 0)                   AS id,
           r.model_id                                  AS model_id,
           r.model_name                                AS model_name,
           r.is_wizard                                 AS is_wizard,
           r.group_id                                  AS group_id,
           (r.group_id IS NULL AND NOT r.no_acl)       AS is_global,
           r.no_acl                                    AS no_acl,
           r.perm_read                                 AS perm_read,
           r.perm_write                                AS perm_write,
           r.perm_create                               AS perm_create,
           r.perm_unlink                               AS perm_unlink,
           CAST(r.acl_count AS integer)                AS acl_count,
           CAST(r.perm_read::integer + r.perm_write::integer
                + r.perm_create::integer + r.perm_unlink::integer AS integer) AS perm_count,
           (CASE WHEN r.perm_read   THEN 'R' ELSE '-' END ||
            CASE WHEN r.perm_write  THEN 'W' ELSE '-' END ||
            CASE WHEN r.perm_create THEN 'C' ELSE '-' END ||
            CASE WHEN r.perm_unlink THEN 'D' ELSE '-' END)  AS rights_code
      FROM matrix_rows r
"""


def abstract_model_names(env):
    """Return (abstract model names, all model names) of the running registry.

    Read from the registry rather than guessed from the database: a model with a
    custom table name (ir.actions.act_window lives in ir_act_window) would be
    mistaken for an abstract one by any name-to-table guess. Names present in
    ir_model but absent from the registry - leftovers of a module that was
    uninstalled - count as abstract here: no table backs them either.
    """
    known = env.registry.models
    abstract = {name for name, model in known.items() if model._abstract}
    return abstract, set(known)


class AccessRightsMatrix(models.Model):
    _name = 'access.rights.matrix'
    _description = 'Access Rights Matrix'
    _auto = False
    _rec_name = 'model_name'
    _order = 'model_name, group_id'

    model_id = fields.Many2one(
        'ir.model', string='Model', readonly=True,
        help='The model these access rights apply to.',
    )
    model_name = fields.Char(
        string='Technical Model', readonly=True,
        help='Technical name of the model, for example res.partner.',
    )
    is_wizard = fields.Boolean(
        string='Wizard', readonly=True,
        help='Ticked for transient models (wizards), whose records are '
             'temporary and cleaned up by the auto-vacuum.',
    )
    is_abstract = fields.Boolean(
        string='Abstract Model', compute='_compute_is_abstract',
        search='_search_is_abstract',
        help='Ticked for abstract models (mixins, report templates). They store '
             'nothing and therefore never need an access control line.',
    )
    group_id = fields.Many2one(
        'res.groups', string='Group', readonly=True,
        help='The group the access control lines are attached to. Empty on '
             'global lines and on models that have no line at all.',
    )
    is_global = fields.Boolean(
        string='Global Line', readonly=True,
        help='Ticked when the access control lines carry no group. Odoo grants '
             'those rights to every user, whatever their groups.',
    )
    no_acl = fields.Boolean(
        string='No Access Rule', readonly=True,
        help='Ticked when the model has no active access control line at all. '
             'Nobody but the superuser can read or change its records.',
    )
    perm_read = fields.Boolean(
        string='Read', readonly=True,
        help='At least one active access control line grants read.',
    )
    perm_write = fields.Boolean(
        string='Write', readonly=True,
        help='At least one active access control line grants write.',
    )
    perm_create = fields.Boolean(
        string='Create', readonly=True,
        help='At least one active access control line grants create.',
    )
    perm_unlink = fields.Boolean(
        string='Delete', readonly=True,
        help='At least one active access control line grants delete.',
    )
    perm_count = fields.Integer(
        string='Permissions', readonly=True, aggregator=False,
        help='How many of the four permissions are granted, from 0 to 4.',
    )
    rights_code = fields.Char(
        string='Rights', readonly=True,
        help='Compact form of the four ticks, for example RW-- or RWCD.',
    )
    acl_count = fields.Integer(
        string='Access Lines', readonly=True, aggregator=False,
        help='Number of active access control lines merged into this row. More '
             'than one means several modules grant rights on the same model to '
             'the same group.',
    )

    @api.depends('model_name')
    def _compute_is_abstract(self):
        abstract, known = abstract_model_names(self.env)
        for line in self:
            line.is_abstract = line.model_name in abstract or line.model_name not in known

    def _search_is_abstract(self, operator, value):
        if operator not in ('=', '!='):
            raise UserError(
                _('The Abstract Model filter only supports = and !=.'))
        abstract, known = abstract_model_names(self.env)
        concrete = sorted(known - abstract)
        wants_abstract = bool(value) == (operator == '=')
        return [('model_name', 'not in' if wants_abstract else 'in', concrete)]

    def _view_sql(self):
        """SQL of the read-only view. Split out so the statement built in
        init() only ever interpolates ``self._`` members."""
        return MATRIX_VIEW_SQL

    def init(self):
        # Read-only database view. The module never writes to ir.model.access:
        # the only value interpolated into the statement is self._table, which
        # comes from _name, and no user input reaches this SQL.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('CREATE VIEW %s AS (%s)' % (self._table, self._view_sql()))
