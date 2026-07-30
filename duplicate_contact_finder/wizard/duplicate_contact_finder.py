# -*- coding: utf-8 -*-
# Part of duplicate_contact_finder. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import psycopg2
import psycopg2.extensions

from odoo import _, fields, models
from odoo.exceptions import UserError

# --- normalisation constants -------------------------------------------------
# A phone shorter than this (once stripped of everything but digits) carries no
# identifying information - extensions like "204" would group half the database.
MIN_PHONE_DIGITS = 7
# Numbers are compared on their last N digits so that "+33 1 23 45 67 89",
# "0033123456789" and "01 23 45 67 89" all collapse to the same key. Nine digits
# is short enough to survive any country prefix and long enough to stay specific.
PHONE_SIGNIFICANT_DIGITS = 9
# "Ltd" or "SA" alone is not a name worth matching on.
MIN_NAME_CHARS = 3
# Contacts listed per group. The group still reports its real size.
MAX_MEMBERS_PER_GROUP = 50
# Hard ceiling on the user-settable cap: the id arrays, the detail query and the
# rows created all scale with it, so it may not be raised without limit.
MAX_GROUPS_HARD_CAP = 2000
# The scan is one pass over the contact table; rather than let a huge database
# run into the worker's own time limit and die with a bare 500, the statements
# are bounded and the timeout is turned into a readable message.
SCAN_STATEMENT_TIMEOUT_MS = 60000

# Latin accent folding used when the PostgreSQL "unaccent" extension is absent.
# Written as (sources, replacement) pairs so the two translate() arguments can
# never drift out of sync.
_FOLD_PAIRS = (
    ('ÀÁÂÃÄÅĀĂĄ', 'A'), ('àáâãäåāăą', 'a'),
    ('ÇĆČ', 'C'), ('çćč', 'c'),
    ('ĎĐ', 'D'), ('ďđ', 'd'),
    ('ÈÉÊËĒĖĘĚ', 'E'), ('èéêëēėęě', 'e'),
    ('ĢĞ', 'G'), ('ģğ', 'g'),
    ('ÌÍÎÏĪĮ', 'I'), ('ìíîïīį', 'i'),
    ('Ķ', 'K'), ('ķ', 'k'),
    ('ĹĻĽŁ', 'L'), ('ĺļľł', 'l'),
    ('ÑŃŅŇ', 'N'), ('ñńņň', 'n'),
    ('ÒÓÔÕÖØŌŐ', 'O'), ('òóôõöøōő', 'o'),
    ('ŔŘ', 'R'), ('ŕř', 'r'),
    ('ŚŞŠ', 'S'), ('śşš', 's'),
    ('ŢŤ', 'T'), ('ţť', 't'),
    ('ÙÚÛÜŪŮŰ', 'U'), ('ùúûüūůű', 'u'),
    ('ÝŸ', 'Y'), ('ýÿ', 'y'),
    ('ŹŻŽ', 'Z'), ('źżž', 'z'),
)
ACCENT_FROM = ''.join(sources for sources, _dst in _FOLD_PAIRS)
ACCENT_TO = ''.join(dst * len(sources) for sources, dst in _FOLD_PAIRS)
# translate() maps one character to one character; these need two, and the
# unaccent extension expands them the same way, so both paths agree.
_FOLD_EXPANSIONS = (('ß', 'ss'), ('Æ', 'AE'), ('æ', 'ae'), ('Œ', 'OE'), ('œ', 'oe'))

# Contact columns holding a telephone number. Odoo 19.0 merged "mobile" into
# "phone", so the columns actually present are resolved at runtime.
PHONE_COLUMNS = ('phone', 'mobile')

# Tables counted as "linked activity" when the matching app is installed. Only
# these hard-coded pairs are ever interpolated into SQL - nothing user supplied.
OPTIONAL_ACTIVITY_SOURCES = (
    ('account_move', 'partner_id'),
    ('sale_order', 'partner_id'),
    ('purchase_order', 'partner_id'),
    ('crm_lead', 'partner_id'),
    ('stock_picking', 'partner_id'),
    ('project_task', 'partner_id'),
)


def _order_groups(rows):
    """Biggest groups first, alternating between criteria inside one size.

    Rows are ``(match_type, match_key, member_count, partner_ids)``. Sorting on
    the match type alone would make a truncated result all-email (e < n < p) and
    hide the criteria the user explicitly enabled, so groups of equal size are
    interleaved. The order is deterministic: two runs agree.
    """
    by_size = {}
    for row in rows:
        by_size.setdefault(row[2], {}).setdefault(row[0], []).append(row)
    ordered = []
    for size in sorted(by_size, reverse=True):
        buckets = [sorted(bucket, key=lambda row: row[1] or '')
                   for _type, bucket in sorted(by_size[size].items())]
        while any(buckets):
            for bucket in buckets:
                if bucket:
                    ordered.append(bucket.pop(0))
    return ordered


class DuplicateContactFinder(models.TransientModel):
    """Read-only scan for probable duplicate contacts.

    Everything is aggregated by PostgreSQL over normalised expressions: the
    partner table is never browsed record by record, and the module never
    writes to, merges or deletes a contact.
    """
    _name = 'duplicate.contact.finder'
    _description = 'Find Duplicate Contacts'

    use_email = fields.Boolean(
        string='Same Email', default=True,
        help='Group contacts whose email is identical once trimmed and lower-cased.')
    use_phone = fields.Boolean(
        string='Same Phone Number', default=True,
        help='Group contacts whose numbers match on digits only: spaces, dashes, '
             'brackets and country prefixes are ignored. Every telephone field of '
             'the contact is pooled, so a phone can match another contact\'s '
             'mobile (Odoo 19.0 keeps a single Phone field).')
    use_name = fields.Boolean(
        string='Same Name', default=True,
        help='Group contacts whose name is identical once case, accents, '
             'punctuation and word order are ignored.')
    include_archived = fields.Boolean(
        string='Include Archived Contacts', default=False,
        help='Off by default: archived contacts are excluded from the scan.')
    contact_kind = fields.Selection(
        [('all', 'Companies and Individuals'),
         ('company', 'Companies Only'),
         ('person', 'Individuals Only')],
        string='Contacts to Scan', default='all', required=True)
    include_addresses = fields.Boolean(
        string='Include Company Addresses', default=False,
        help='Invoice, delivery and other addresses attached to a company are '
             'skipped by default: they legitimately repeat the phone or name of '
             'their parent company.')
    max_groups = fields.Integer(
        string='Maximum Groups Reported', default=200, required=True,
        help='Safety cap. When more duplicate groups exist than this, the '
             'largest ones are reported and the result is flagged as truncated. '
             'It cannot be raised above 2000: everything the scan builds grows '
             'with it.')

    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Scanned')],
        default='draft', required=True, readonly=True)
    scanned_on = fields.Datetime(string='Scanned On', readonly=True)
    group_ids = fields.One2many(
        'duplicate.contact.group', 'finder_id', string='Duplicate Groups', readonly=True)
    group_count = fields.Integer(string='Groups Found', readonly=True)
    contact_count = fields.Integer(string='Contacts Involved', readonly=True)
    truncated = fields.Boolean(string='Result Truncated', readonly=True)
    truncation_note = fields.Char(string='Truncation Note', readonly=True)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _flush_orm(self):
        """Make pending ORM writes visible to the raw SQL below."""
        env = self.env
        if hasattr(env, 'flush_all'):
            env.flush_all()
        else:  # 14.0 / 15.0
            env['res.partner'].flush()

    def _has_unaccent(self):
        """True when the PostgreSQL unaccent() function can be called."""
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute("SELECT unaccent('e')")
            return True
        except psycopg2.Error:
            return False

    def _accent_expression(self, column):
        """SQL expression folding accents away from ``column``."""
        if self._has_unaccent():
            return 'unaccent({col})'.format(col=column)
        expression = column
        for index in range(len(_FOLD_EXPANSIONS)):
            expression = 'replace({expr}, %(fold_from_{i})s, %(fold_to_{i})s)'.format(
                expr=expression, i=index)
        return 'translate({expr}, %(accent_from)s, %(accent_to)s)'.format(expr=expression)

    def _company_clause(self, alias):
        """The company half of base.res_partner_rule, for table alias ``alias``.

        The standard rule is
        ``['|', ('partner_share', '=', False), ('company_id', 'in', company_ids + [False])]``
        on 14.0-16.0 and the ``parent_of`` variant from 17.0 on. This clause is
        never broader than either: contacts of a *parent* company in a company
        hierarchy are not expanded, so on 17.0+ the scan can miss a duplicate
        the Contacts list would show, but it can never show one it hides.
        """
        return ('({a}.partner_share = FALSE OR {a}.company_id IS NULL '
                'OR {a}.company_id IN %(company_ids)s)').format(a=alias)

    def _scan_scope(self):
        """WHERE fragment + parameters selecting the contacts in scope."""
        clauses = [self._company_clause('p')]
        params = {
            'company_ids': tuple(self.env.companies.ids) or (0,),
            'accent_from': ACCENT_FROM,
            'accent_to': ACCENT_TO,
            'min_phone_digits': MIN_PHONE_DIGITS,
            'phone_digits': PHONE_SIGNIFICANT_DIGITS,
            'min_name_chars': MIN_NAME_CHARS,
        }
        for index, (source, target) in enumerate(_FOLD_EXPANSIONS):
            params['fold_from_%s' % index] = source
            params['fold_to_%s' % index] = target
        if not self.include_archived:
            clauses.append('p.active = TRUE')
        if self.contact_kind == 'company':
            clauses.append('COALESCE(p.is_company, FALSE) = TRUE')
        elif self.contact_kind == 'person':
            clauses.append('COALESCE(p.is_company, FALSE) = FALSE')
        if not self.include_addresses:
            clauses.append("(p.parent_id IS NULL OR COALESCE(p.type, 'contact') = 'contact')")
        # base.res_partner_rule_private_employee (14.0-16.0): private addresses
        # are employee home data, gated behind a group that Settings access does
        # NOT grant. The group and the 'private' type were both dropped in 17.0,
        # so the ref() lookup makes this clause a no-op there.
        if self.env.ref('base.group_private_addresses', raise_if_not_found=False) \
                and not self.env.user.has_group('base.group_private_addresses'):
            clauses.append("COALESCE(p.type, 'contact') <> 'private'")
        return ' AND '.join(clauses), params

    # ------------------------------------------------------------------
    # aggregation queries - one grouped statement per criterion
    # ------------------------------------------------------------------
    def _fetch_email_groups(self, limit):
        where, params = self._scan_scope()
        params['limit'] = limit
        self.env.cr.execute("""
            SELECT lower(btrim(p.email))                          AS match_key,
                   count(*)                                       AS member_count,
                   (array_agg(p.id ORDER BY p.id))[1:{members}]    AS partner_ids
              FROM res_partner p
             WHERE {where}
               AND p.email IS NOT NULL
               AND btrim(p.email) <> ''
               AND strpos(p.email, '@') > 1
          GROUP BY 1
            HAVING count(*) > 1
          ORDER BY member_count DESC, match_key
             LIMIT %(limit)s
        """.format(where=where, members=MAX_MEMBERS_PER_GROUP), params)
        return self.env.cr.fetchall()

    def _phone_columns(self):
        """The phone columns this Odoo actually has (19.0 merged mobile into phone)."""
        partner_fields = self.env['res.partner']._fields
        return [name for name in PHONE_COLUMNS if name in partner_fields]

    def _fetch_phone_groups(self, limit):
        columns = self._phone_columns()
        if not columns:
            return []
        where, params = self._scan_scope()
        params['limit'] = limit
        # phone and mobile are pooled: one contact's mobile must be able to
        # match another contact's phone. Column names come from PHONE_COLUMNS.
        digits = "\n                UNION ALL\n".join("""
                SELECT p.id AS partner_id,
                       regexp_replace(p.{column}, '[^0-9]', '', 'g') AS d
                  FROM res_partner p
                 WHERE {where} AND p.{column} IS NOT NULL""".format(column=column, where=where)
            for column in columns)
        self.env.cr.execute("""
            WITH digits AS ({digits}
            ),
            keys AS (
                SELECT DISTINCT partner_id,
                       CASE WHEN length(d) > %(phone_digits)s
                            THEN right(d, %(phone_digits)s) ELSE d END AS match_key
                  FROM digits
                 WHERE length(d) >= %(min_phone_digits)s
            )
            SELECT match_key,
                   count(*)                                           AS member_count,
                   (array_agg(partner_id ORDER BY partner_id))[1:{members}] AS partner_ids
              FROM keys
          GROUP BY match_key
            HAVING count(*) > 1
          ORDER BY member_count DESC, match_key
             LIMIT %(limit)s
        """.format(digits=digits, members=MAX_MEMBERS_PER_GROUP), params)
        return self.env.cr.fetchall()

    def _fetch_name_groups(self, limit):
        where, params = self._scan_scope()
        params['limit'] = limit
        # normalise -> split on anything that is not a letter or a digit ->
        # sort the words, so "Ferreira, José" and "jose ferreira" collapse.
        self.env.cr.execute("""
            WITH normalised AS (
                SELECT p.id AS partner_id,
                       btrim(regexp_replace(lower({accent}), '[^[:alnum:]]+', ' ', 'g')) AS n
                  FROM res_partner p
                 WHERE {where} AND p.name IS NOT NULL AND btrim(p.name) <> ''
            ),
            keys AS (
                SELECT partner_id,
                       (SELECT string_agg(word, ' ' ORDER BY word)
                          FROM unnest(string_to_array(n, ' ')) AS word
                         WHERE word <> '') AS match_key
                  FROM normalised
                 WHERE length(replace(n, ' ', '')) >= %(min_name_chars)s
            )
            SELECT match_key,
                   count(*)                                           AS member_count,
                   (array_agg(partner_id ORDER BY partner_id))[1:{members}] AS partner_ids
              FROM keys
             WHERE match_key IS NOT NULL AND match_key <> ''
          GROUP BY match_key
            HAVING count(*) > 1
          ORDER BY member_count DESC, match_key
             LIMIT %(limit)s
        """.format(where=where, accent=self._accent_expression('p.name'),
                   members=MAX_MEMBERS_PER_GROUP), params)
        return self.env.cr.fetchall()

    def _activity_sources(self):
        """The optional tables that exist here, and whether they carry a company.

        Only the hard-coded pairs of OPTIONAL_ACTIVITY_SOURCES can ever come
        back, so the names are safe to interpolate into the counter SQL.
        """
        wanted = OPTIONAL_ACTIVITY_SOURCES + tuple(
            (table, 'company_id') for table, _col in OPTIONAL_ACTIVITY_SOURCES)
        self.env.cr.execute("""
            SELECT table_name, column_name
              FROM information_schema.columns
             WHERE table_schema = 'public' AND (table_name, column_name) IN %s
        """, (wanted,))
        found = self.env.cr.fetchall()
        with_company = set(table for table, column in found if column == 'company_id')
        return sorted((table, column, table in with_company)
                      for table, column in found
                      if (table, column) in OPTIONAL_ACTIVITY_SOURCES)

    def _fetch_partner_details(self, partner_ids):
        """One statement returning every column the report shows, activity included."""
        if not partner_ids:
            return {}
        # Messages and activities carry no company of their own; the business
        # documents do, and are counted only for the companies the user may see.
        counters = [
            "(SELECT count(*) FROM mail_message m "
            " WHERE m.model = 'res.partner' AND m.res_id = p.id)",
            "(SELECT count(*) FROM mail_activity a "
            " WHERE a.res_model = 'res.partner' AND a.res_id = p.id)",
            "(SELECT count(*) FROM res_partner c WHERE c.parent_id = p.id AND {scope})".format(
                scope=self._company_clause('c')),
        ]
        for table, column, has_company in self._activity_sources():
            counters.append(
                '(SELECT count(*) FROM {table} t WHERE t.{column} = p.id{scope})'.format(
                    table=table, column=column,
                    scope=(' AND (t.company_id IS NULL OR t.company_id IN %(company_ids)s)'
                           if has_company else '')))
        columns = self._phone_columns()
        self.env.cr.execute("""
            SELECT p.id, p.name, p.email, {phone}, {mobile}, p.create_date,
                   p.active, COALESCE(p.is_company, FALSE),
                   EXISTS (SELECT 1 FROM res_users u WHERE u.partner_id = p.id),
                   {counters}
              FROM res_partner p
             WHERE p.id = ANY(%(partner_ids)s)
        """.format(
            phone='p.phone' if 'phone' in columns else 'NULL::varchar',
            mobile='p.mobile' if 'mobile' in columns else 'NULL::varchar',
            counters=' + '.join(counters),
        ), {
            'partner_ids': list(partner_ids),
            'company_ids': tuple(self.env.companies.ids) or (0,),
        })
        details = {}
        for row in self.env.cr.fetchall():
            details[row[0]] = {
                'partner_id': row[0],
                'partner_name': row[1] or '',
                'partner_email': row[2] or '',
                'partner_phone': row[3] or '',
                'partner_mobile': row[4] or '',
                'partner_create_date': row[5],
                'partner_active': row[6],
                'is_company': row[7],
                'is_user': row[8],
                'activity_count': row[9],
            }
        return details

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def action_scan(self):
        self.ensure_one()
        if not (self.use_email or self.use_phone or self.use_name):
            raise UserError(_('Select at least one criterion to match contacts on.'))
        if self.max_groups < 1:
            raise UserError(_('The maximum number of groups must be at least 1.'))
        if self.max_groups > MAX_GROUPS_HARD_CAP:
            raise UserError(_(
                'The maximum number of groups cannot exceed %(cap)s. Narrow the '
                'scan down instead: one criterion at a time, or companies only.'
            ) % {'cap': MAX_GROUPS_HARD_CAP})

        self.group_ids.unlink()
        self._flush_orm()

        limit = self.max_groups
        timeout = self.env.context.get('duplicate_finder_timeout_ms',
                                       SCAN_STATEMENT_TIMEOUT_MS)
        raw = []
        try:
            # SET LOCAL is undone with the savepoint, so the ceiling cannot leak
            # into the rest of the transaction.
            with self.env.cr.savepoint():
                self.env.cr.execute('SET LOCAL statement_timeout = %s', (timeout,))
                if self.use_email:
                    raw += [('email',) + row for row in self._fetch_email_groups(limit + 1)]
                if self.use_phone:
                    raw += [('phone',) + row for row in self._fetch_phone_groups(limit + 1)]
                if self.use_name:
                    raw += [('name',) + row for row in self._fetch_name_groups(limit + 1)]

                truncated = len(raw) > limit
                raw = _order_groups(raw)[:limit]

                wanted = set()
                for _type, _key, _count, ids in raw:
                    wanted.update(ids[:MAX_MEMBERS_PER_GROUP])
                details = self._fetch_partner_details(wanted)
                self.env.cr.execute('SET LOCAL statement_timeout = DEFAULT')
        except psycopg2.extensions.QueryCanceledError:
            raise UserError(_(
                'The scan did not finish within %(seconds)s seconds on this '
                'database. Narrow it down: scan one criterion at a time, or '
                'restrict it to companies or to individuals.'
            ) % {'seconds': int(timeout / 1000) or 1})

        group_vals = []
        involved = set()
        for match_type, match_key, member_count, ids in raw:
            members = [details[pid] for pid in ids[:MAX_MEMBERS_PER_GROUP]
                       if pid in details]
            if len(members) < 2:
                continue  # the contacts vanished between the two queries
            members.sort(key=lambda m: (-m['activity_count'],
                                        m['partner_create_date'] or fields.Datetime.now(),
                                        m['partner_id']))
            involved.update(m['partner_id'] for m in members)
            top = members[0] if members[0]['activity_count'] else None
            dates = [m['partner_create_date'] for m in members if m['partner_create_date']]
            group_vals.append({
                'finder_id': self.id,
                'match_type': match_type,
                'match_value': match_key,
                'partner_count': member_count,
                'listed_count': len(members),
                'members_truncated': member_count > len(members),
                'first_created': min(dates) if dates else False,
                'last_created': max(dates) if dates else False,
                'top_partner_id': top['partner_id'] if top else False,
                'top_activity_count': top['activity_count'] if top else 0,
                'member_ids': [(0, 0, dict(member,
                                           is_most_active=bool(top) and member is members[0]))
                               for member in members],
            })
        self.env['duplicate.contact.group'].create(group_vals)

        note = False
        if truncated:
            note = _('More duplicate groups were found than the cap of %(cap)s. '
                     'The largest groups are listed; raise "Maximum Groups Reported" '
                     'or narrow the criteria to see the rest.') % {'cap': limit}
        self.write({
            'state': 'done',
            'scanned_on': fields.Datetime.now(),
            'group_count': len(group_vals),
            'contact_count': len(involved),
            'truncated': truncated,
            'truncation_note': note,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Find Duplicate Contacts'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_reset(self):
        self.ensure_one()
        self.group_ids.unlink()
        self.write({
            'state': 'draft',
            'group_count': 0,
            'contact_count': 0,
            'truncated': False,
            'truncation_note': False,
            'scanned_on': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Find Duplicate Contacts'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }


class DuplicateContactGroup(models.TransientModel):
    _name = 'duplicate.contact.group'
    _description = 'Duplicate Contact Group'
    _order = 'partner_count desc, match_type, id'
    _rec_name = 'match_value'

    finder_id = fields.Many2one(
        'duplicate.contact.finder', string='Scan', required=True,
        ondelete='cascade', index=True)
    match_type = fields.Selection(
        [('email', 'Same Email'),
         ('phone', 'Same Phone Number'),
         ('name', 'Same Name')],
        string='Matched On', required=True, readonly=True)
    match_value = fields.Char(
        string='Matched Value', readonly=True,
        help='The normalised value the contacts of this group have in common.')
    partner_count = fields.Integer(string='Contacts', readonly=True)
    listed_count = fields.Integer(string='Listed', readonly=True)
    members_truncated = fields.Boolean(string='Members Truncated', readonly=True)
    member_ids = fields.One2many(
        'duplicate.contact.member', 'group_id', string='Duplicate Contacts', readonly=True)
    first_created = fields.Datetime(string='Oldest Contact', readonly=True)
    last_created = fields.Datetime(string='Newest Contact', readonly=True)
    top_partner_id = fields.Many2one(
        'res.partner', string='Most Linked Activity', readonly=True,
        help='The listed contact of this group with the most linked records - on '
             'a group too large to list in full, only the listed contacts are '
             'compared. Empty when none of them has any linked record.')
    top_activity_count = fields.Integer(string='Linked Records', readonly=True)

    def _partner_ids(self):
        return self.member_ids.mapped('partner_id').ids

    def action_open_contacts(self):
        """Open the contacts of this group in the standard Contacts list."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Duplicate Contacts'),
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self._partner_ids())],
            'context': {'active_test': False},
            'target': 'current',
        }

    def action_open_merge_wizard(self):
        """Hand this group over to Odoo's own Merge Contacts wizard.

        This module never merges anything itself: merging rewrites foreign keys
        and deletes records, so it is left to the standard wizard where the user
        picks the destination contact and confirms.
        """
        self.ensure_one()
        partner_ids = self._partner_ids()
        if len(partner_ids) < 2:
            raise UserError(_('At least two contacts are needed to merge.'))
        if not self.env.user.has_group('base.group_partner_manager'):
            raise UserError(_(
                "Odoo's Merge Contacts wizard requires the contact management "
                "access right. Ask an administrator to grant it before merging."))
        action = self.env['ir.actions.act_window']._for_xml_id('base.action_partner_merge')
        action['context'] = {
            'active_model': 'res.partner',
            'active_ids': partner_ids,
            'active_id': partner_ids[0],
            'active_test': False,
        }
        action['target'] = 'new'
        return action


class DuplicateContactMember(models.TransientModel):
    _name = 'duplicate.contact.member'
    _description = 'Duplicate Contact Group Member'
    _order = 'activity_count desc, partner_create_date, id'
    _rec_name = 'partner_name'

    group_id = fields.Many2one(
        'duplicate.contact.group', string='Group', required=True,
        ondelete='cascade', index=True)
    partner_id = fields.Many2one('res.partner', string='Contact', readonly=True)
    partner_name = fields.Char(string='Name', readonly=True)
    partner_email = fields.Char(string='Email', readonly=True)
    partner_phone = fields.Char(string='Phone', readonly=True)
    partner_mobile = fields.Char(string='Mobile', readonly=True)
    partner_create_date = fields.Datetime(string='Created On', readonly=True)
    partner_active = fields.Boolean(string='Active', readonly=True)
    is_company = fields.Boolean(string='Is a Company', readonly=True)
    is_user = fields.Boolean(
        string='Has a Login', readonly=True,
        help='This contact is linked to a user account.')
    activity_count = fields.Integer(
        string='Linked Records', readonly=True,
        help='Messages, activities, child contacts and business documents '
             '(invoices, orders, leads, transfers, tasks) pointing at this contact.')
    is_most_active = fields.Boolean(string='Most Linked Activity', readonly=True)

    def action_open_partner(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.partner_name or _('Contact'),
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'active_test': False},
        }
