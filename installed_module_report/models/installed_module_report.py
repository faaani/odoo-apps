# -*- coding: utf-8 -*-
# Part of installed_module_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from collections import defaultdict

from odoo import _, api, fields, models, tools

# How many dependency names the one-line summary columns show before they say
# "+N more". The Many2many fields on the form always carry the complete list.
PREVIEW_LIMIT = 8

# Author strings that mean "published by Odoo S.A.". Compared against the author
# after lower-casing and collapsing whitespace, as a WHOLE string: many genuine
# third-party vendors have names that merely start with "Odoo" (Odoo Mates,
# Odoo India, ...), so a prefix match would credit their modules to Odoo.
# A module co-authored by Odoo and somebody else ("Odoo S.A., Tecnativa") is
# deliberately NOT in this list and lands in "other third party": an inventory
# that exists to find third-party code should over-report, not under-report.
ODOO_AUTHORS = (
    'odoo',
    'odoo s.a.',
    'odoo s.a',
    'odoo sa',
    'odoo sa.',
    'odoo ps',
    'openerp',
    'openerp s.a.',
    'openerp s.a',
    'openerp sa',
    'tiny sprl',
)

# The three licence values in Odoo's own manifest list that are not open source.
# They drive both the "Proprietary" licence type and the Enterprise origin.
PROPRIETARY_LICENSES = ('OEEL-1', 'OPL-1', 'Other proprietary')

# Odoo records no install date. The closest fact in the database is the creation
# date of the oldest external ID (ir_model_data row) the module wrote, which is
# stamped when the module is first loaded. Modules that create no external ID at
# all - a handful of pure-Python ones - therefore have no date, and the column
# stays empty rather than guessing.
#
# install_date is a correlated sub-query on purpose. Written as a grouped CTE it
# reads well, but the planner cannot push the row filter into it: fetching a
# single page of the report then aggregates the WHOLE of ir_model_data, which is
# hundreds of thousands of rows on a real database. The correlated form probes
# ir_model_data_module_name_uniq_index (module, name) per installed module
# instead, so the cost follows the number of installed modules.
REPORT_VIEW_SQL = """
    WITH dep AS (
        SELECT d.module_id                                AS module_id,
               COUNT(*)::integer                          AS dependency_count
          FROM ir_module_module_dependency d
      GROUP BY d.module_id
    ),
    rdep AS (
        SELECT d.name                                     AS name,
               COUNT(*)::integer                          AS reverse_dependency_count
          FROM ir_module_module_dependency d
          JOIN ir_module_module dm ON dm.id = d.module_id
         WHERE dm.state IN ('installed', 'to upgrade', 'to remove')
      GROUP BY d.name
    ),
    module_rows AS (
        SELECT m.id                                       AS id,
               m.id                                       AS module_id,
               m.name                                     AS technical_name,
               m.latest_version                           AS installed_version,
               m.author                                   AS author,
               m.license                                  AS license,
               m.category_id                              AS category_id,
               m.state                                    AS module_state,
               COALESCE(m.application, FALSE)             AS application,
               COALESCE(m.auto_install, FALSE)            AS auto_install,
               (SELECT MIN(imd.create_date)
                  FROM ir_model_data imd
                 WHERE imd.module = m.name)               AS install_date,
               COALESCE(dep.dependency_count, 0)          AS dependency_count,
               COALESCE(rdep.reverse_dependency_count, 0) AS reverse_dependency_count,
               btrim(lower(regexp_replace(COALESCE(m.author, ''),
                                          '[[:space:]]+', ' ', 'g')))
                                                          AS normalised_author
          FROM ir_module_module m
          LEFT JOIN dep  ON dep.module_id = m.id
          LEFT JOIN rdep ON rdep.name = m.name
         WHERE m.state IN ('installed', 'to upgrade', 'to remove')
    ),
    classified AS (
        SELECT r.*,
               CASE
                   WHEN strpos(r.normalised_author,
                               'odoo community association') > 0
                        OR strpos(r.normalised_author, '(oca)') > 0
                       THEN 'oca'
                   WHEN r.normalised_author = ''
                       THEN 'unknown'
                   WHEN r.normalised_author IN %(odoo_authors)s
                        AND r.license IN %(proprietary)s
                       THEN 'enterprise'
                   WHEN r.normalised_author IN %(odoo_authors)s
                       THEN 'odoo'
                   ELSE 'third'
               END                                        AS origin,
               CASE
                   WHEN COALESCE(r.license, '') = ''      THEN 'undeclared'
                   WHEN r.license IN %(proprietary)s      THEN 'proprietary'
                   ELSE 'open_source'
               END                                        AS license_kind
          FROM module_rows r
    )
    SELECT c.id,
           c.module_id,
           c.technical_name,
           c.installed_version,
           c.author,
           c.license,
           c.category_id,
           c.module_state,
           c.application,
           c.auto_install,
           c.install_date,
           c.dependency_count,
           c.reverse_dependency_count,
           c.origin,
           c.license_kind,
           (c.origin NOT IN ('odoo', 'enterprise'))       AS is_third_party,
           (COALESCE(c.license, '') <> 'LGPL-3')          AS nonstandard_license,
           (NOT c.application
            AND NOT c.auto_install
            AND c.reverse_dependency_count = 0)           AS standalone
      FROM classified c
"""


def _sql_tuple(values):
    """Render a Python tuple of plain strings as an SQL literal list.

    The values come from the two module-level constants above - never from user
    input - and are single-quote escaped anyway so the literal cannot be broken
    out of. They are inlined rather than bound because CREATE VIEW freezes the
    statement: a bound parameter would not survive into the stored view.
    """
    return '(%s)' % ', '.join("'%s'" % v.replace("'", "''") for v in values)


# The base.group_system access rule shipped in security/ is load-bearing, not a
# preference: ir.module.module is group_system-only in Odoo's own ACL, and the
# ORM does not carry that ACL through an _auto=False view. Widening the rule
# would re-expose author, licence, version and state to users core keeps them
# from.
class InstalledModuleReport(models.Model):
    _name = 'installed.module.report'
    _description = 'Installed Modules Report'
    _auto = False
    _rec_name = 'technical_name'
    _order = 'technical_name'

    module_id = fields.Many2one(
        'ir.module.module', string='Module', readonly=True,
        help='The module list entry this line reports on.',
    )
    technical_name = fields.Char(
        string='Technical Name', readonly=True,
        help='The name of the directory the module lives in, and the name other '
             'modules use to depend on it.',
    )
    # Read through the relation rather than out of the SQL view: shortdesc is a
    # translated field, stored as jsonb from Odoo 16 on, and going through the
    # ORM keeps the reader's language working on every supported series.
    module_name = fields.Char(
        string='Module Name', related='module_id.shortdesc', readonly=True,
        help='The title shown in the Apps screen.',
    )
    installed_version = fields.Char(
        string='Installed Version', readonly=True,
        help='Version currently installed on this database, as recorded when the '
             'module was last loaded.',
    )
    author = fields.Char(
        string='Author', readonly=True,
        help='Author declared in the module manifest. Up to Odoo 18 a module that '
             'declares no author at all is recorded as "Odoo S.A.".',
    )
    license = fields.Char(
        string='Licence', readonly=True,
        help='Licence declared in the module manifest.',
    )
    # 'undeclared' is defensive only: Odoo defaults a missing manifest licence to
    # LGPL-3 on every supported series, so no module loaded from disk can land in
    # that bucket. There is deliberately no filter for it in the search view.
    license_kind = fields.Selection(
        [
            ('open_source', 'Open source'),
            ('proprietary', 'Proprietary'),
            ('undeclared', 'Not declared'),
        ],
        string='Licence Type', readonly=True,
        help='Proprietary covers OPL-1, OEEL-1 and "Other proprietary"; every '
             'other declared licence is counted as open source. Odoo replaces a '
             'missing licence with LGPL-3, so "Not declared" stays empty in '
             'practice.',
    )
    nonstandard_license = fields.Boolean(
        string='Non-standard Licence', readonly=True,
        help='Ticked for every module whose licence is not LGPL-3, the licence '
             'Odoo Community itself ships under: stronger copyleft (GPL, AGPL), '
             'proprietary (OPL-1, OEEL-1, other), or no licence at all. Odoo '
             'Enterprise modules are OEEL-1 and appear here by design.',
    )
    origin = fields.Selection(
        [
            ('odoo', 'Odoo S.A. (core)'),
            ('enterprise', 'Odoo S.A. (Enterprise)'),
            ('oca', 'Odoo Community Association (OCA)'),
            ('third', 'Other third party'),
            ('unknown', 'Author not declared'),
        ],
        string='Origin', readonly=True,
        help='Worked out from the declared author, refined by the licence: an '
             'author of Odoo S.A. with an OPL-1 or OEEL-1 licence is reported as '
             'Enterprise, with any other licence as core. An author mentioning '
             '"Odoo Community Association" or "(OCA)" is reported as OCA. '
             'Anything else - including a module co-authored by Odoo and a '
             'partner - is reported as third party. It reads the manifest, so a '
             'manifest that is wrong makes this line wrong. Up to Odoo 18 a '
             'module that declares no author at all is recorded by Odoo itself '
             'as "Odoo S.A." and is therefore reported as core, so "Author not '
             'declared" only ever appears on Odoo 19.',
    )
    is_third_party = fields.Boolean(
        string='Third Party', readonly=True,
        help='Ticked for every module not published by Odoo S.A., OCA modules '
             'included. Up to Odoo 18 a module with no declared author is '
             'recorded by Odoo as "Odoo S.A." and is reported as core, not as '
             'third party.',
    )
    category_id = fields.Many2one(
        'ir.module.category', string='Category', readonly=True,
        help='Category declared in the module manifest.',
    )
    module_state = fields.Selection(
        [
            ('installed', 'Installed'),
            ('to upgrade', 'To be upgraded'),
            ('to remove', 'To be removed'),
        ],
        string='Status', readonly=True,
        help='Modules queued for upgrade or removal are still installed right '
             'now, so they are listed here too.',
    )
    application = fields.Boolean(
        string='Application', readonly=True,
        help='Ticked for modules that declare themselves an app, the ones with a '
             'tile in the Apps screen.',
    )
    auto_install = fields.Boolean(
        string='Auto Installed', readonly=True,
        help='Ticked for link modules Odoo installs by itself once their '
             'dependencies are present.',
    )
    install_date = fields.Datetime(
        string='Installed On (approx.)', readonly=True,
        help='Odoo stores no install date. This is the creation date of the '
             'oldest external ID the module wrote, which is stamped the first '
             'time the module is loaded. Empty for modules that create no '
             'external ID.',
    )
    dependency_count = fields.Integer(
        string='Declared Dependencies', readonly=True, group_operator=False,
        help='How many modules this module declares as a direct dependency in '
             'its manifest, INCLUDING any that is not installed on this '
             'database. It is therefore higher than the "Depends On" list when a '
             'declared dependency is missing - which is itself worth looking '
             'into. The reverse column counts installed modules only.',
    )
    reverse_dependency_count = fields.Integer(
        string='Depended On By', readonly=True, group_operator=False,
        help='How many INSTALLED modules declare this module as a direct '
             'dependency. Modules present on disk but not installed are not '
             'counted.',
    )
    standalone = fields.Boolean(
        string='Not Part Of Any App', readonly=True,
        help='Ticked when the module is not an application itself, was not '
             'auto-installed as a link module, and no installed module depends '
             'on it - so it was installed on purpose and nothing else needs it. '
             'Only DIRECT dependencies are considered.',
    )
    # Computed, not stored: these four columns cannot be sorted on, and Odoo
    # hides the sort arrow accordingly. Never pass order='dependency_names' to
    # search() - 14.0-17.0 warn and drop the sort, 18.0/19.0 raise.
    dependency_ids = fields.Many2many(
        'installed.module.report', string='Depends On (installed)',
        compute='_compute_dependency_ids',
        help='The direct dependencies of this module that are themselves '
             'installed. A declared dependency that is missing from this '
             'database is counted in "Declared Dependencies" but cannot appear '
             'here.',
    )
    dependency_names = fields.Char(
        string='Depends On (summary)', compute='_compute_dependency_ids',
        help='Technical names of the direct dependencies exactly as declared in '
             'the manifest, whether or not they are installed.',
    )
    reverse_dependency_ids = fields.Many2many(
        'installed.module.report', string='Required By',
        compute='_compute_reverse_dependency_ids',
        help='The installed modules that declare this module as a direct '
             'dependency.',
    )
    reverse_dependency_names = fields.Char(
        string='Required By (summary)', compute='_compute_reverse_dependency_ids',
        help='Technical names of the installed modules that depend on this one.',
    )

    # ------------------------------------------------------------------
    # Dependency resolution
    # ------------------------------------------------------------------
    @staticmethod
    def _format_name_preview(names):
        """One-line summary of a dependency list, capped at PREVIEW_LIMIT."""
        if not names:
            return False
        if len(names) <= PREVIEW_LIMIT:
            return ', '.join(names)
        return _('%s, +%s more') % (
            ', '.join(names[:PREVIEW_LIMIT]), len(names) - PREVIEW_LIMIT)

    @api.depends('module_id')
    def _compute_dependency_ids(self):
        """Direct dependencies: two queries for the whole recordset."""
        self.dependency_ids = self.browse()
        self.dependency_names = False
        module_ids = [line.module_id.id for line in self if line.module_id]
        if not module_ids:
            return
        # One grouped read of the dependency table for every line on screen.
        self.env.cr.execute("""
            SELECT d.module_id, d.name
              FROM ir_module_module_dependency d
             WHERE d.module_id IN %s
          ORDER BY d.name
        """, (tuple(module_ids),))
        names_per_module = defaultdict(list)
        for module_id, dependency_name in self.env.cr.fetchall():
            names_per_module[module_id].append(dependency_name)
        wanted = {name for names in names_per_module.values() for name in names}
        # Resolved through search(), so the reader's access rights apply and a
        # dependency that is declared but not installed simply drops out.
        installed = {
            line.technical_name: line
            for line in self.search([('technical_name', 'in', list(wanted))])
        } if wanted else {}
        for line in self:
            names = names_per_module.get(line.module_id.id, [])
            line.dependency_names = self._format_name_preview(names)
            # browse once: repeated |= on a growing recordset is quadratic, and
            # a core module can be depended on by hundreds of others.
            line.dependency_ids = self.browse(
                [installed[name].id for name in names if name in installed])

    @api.depends('technical_name')
    def _compute_reverse_dependency_ids(self):
        """Installed modules depending on these ones: two queries in total."""
        self.reverse_dependency_ids = self.browse()
        self.reverse_dependency_names = False
        names = [line.technical_name for line in self if line.technical_name]
        if not names:
            return
        self.env.cr.execute("""
            SELECT d.name, d.module_id
              FROM ir_module_module_dependency d
             WHERE d.name IN %s
        """, (tuple(names),))
        raw = self.env.cr.fetchall()
        if not raw:
            return
        # The report view only exposes installed modules, so searching it here
        # is what filters out dependents that are merely present on disk.
        dependents = {
            line.module_id.id: line
            for line in self.search(
                [('module_id', 'in', list({row[1] for row in raw}))])
        }
        lines_per_name = defaultdict(list)
        for name, module_id in raw:
            if module_id in dependents:
                lines_per_name[name].append(dependents[module_id])
        for lines in lines_per_name.values():
            lines.sort(key=lambda line: line.technical_name or '')
        for line in self:
            found = lines_per_name.get(line.technical_name, [])
            line.reverse_dependency_names = self._format_name_preview(
                [dependent.technical_name for dependent in found])
            # already sorted above; browse() keeps the order and avoids the
            # quadratic cost of unioning one record at a time
            line.reverse_dependency_ids = self.browse(
                [dependent.id for dependent in found])

    # ------------------------------------------------------------------
    def _view_sql(self):
        """SQL of the read-only view. Split out so that the statement built in
        init() only interpolates self._table plus the two constant lists."""
        return REPORT_VIEW_SQL % {
            'odoo_authors': _sql_tuple(ODOO_AUTHORS),
            'proprietary': _sql_tuple(PROPRIETARY_LICENSES),
        }

    def init(self):
        # Read-only database view over ir_module_module and its dependency
        # table. The module never writes to either one, and never installs,
        # upgrades or uninstalls anything. Nothing interpolated into this
        # statement comes from user input: self._table is derived from _name and
        # the two lists are module-level constants.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            'CREATE VIEW %s AS (%s)' % (self._table, self._view_sql()))
