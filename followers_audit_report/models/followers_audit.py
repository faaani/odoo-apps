# -*- coding: utf-8 -*-
# Part of followers_audit_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
from collections import defaultdict

from odoo import _, api, fields, models, release
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Default cap on how many followers (resp. records) a run ranks and materialises.
# The ranking and the LIMIT both happen in SQL, so a database with millions of
# mail.followers rows never builds millions of Python dicts. Override with the
# ir.config_parameter below; store 0 to disable the cap entirely.
DEFAULT_LINE_LIMIT = 2000
LIMIT_PARAM = 'followers_audit_report.line_limit'

# 18.0 renamed the list view type from "tree" to "list"; act_window.view_mode
# validates against that name, so derive it instead of forking the file.
LIST_MODE = 'list' if release.version_info[0] >= 18 else 'tree'

# Integer fields default to a "sum" aggregate in grouped list views. Summing a
# per-person total once per document type, or summing database ids, produces
# numbers that mean nothing, so those columns opt out. 18.0 renamed the keyword
# group_operator -> aggregator.
NO_AGGREGATE = ({'aggregator': False} if release.version_info[0] >= 18
                else {'group_operator': False})

# The count has to be requested under an explicit alias so that ORDER BY can
# name it: orderby='__count desc' raises ValueError on 14.0-16.0, where only
# groupby fields and *named* aggregates reach _read_group_prepare. Three traps
# in that spelling, each one verified against a failure:
#  * the aggregated field must NOT be one of the groupby fields - 14.0-16.0 skip
#    such an aggregate entirely ("if fname in groupby_fields: continue"), so the
#    alias would never exist and ORDER BY would raise. 'id' is never grouped on.
#  * the alias must not be a substring of "desc", because 17.0+ rewrites the
#    order term with a plain str.replace().
#  * count(id) is the row count, which is what both reports mean by "followers".
COUNT_ALIAS = 'fa_count'
COUNT_SPEC = '%s:count(id)' % COUNT_ALIAS


def _line_limit(env):
    """Maximum number of followers/records to rank per run. 0 means "no cap".

    The raw parameter string is parsed here rather than relying on
    ``get_param(key, default)``: that helper returns the default for any falsy
    stored value, which would make an explicit "0" (uncapped) impossible.
    """
    raw = env['ir.config_parameter'].get_param(LIMIT_PARAM)
    if raw in (None, False, ''):
        return DEFAULT_LINE_LIMIT
    try:
        limit = int(str(raw).strip())
    except (TypeError, ValueError):
        _logger.warning(
            'Followers Audit: ignoring non-numeric %s=%r, using %s',
            LIMIT_PARAM, raw, DEFAULT_LINE_LIMIT)
        return DEFAULT_LINE_LIMIT
    return max(limit, 0)


def _model_labels(env, model_names):
    """Resolve technical model names to (label, ir.model id) in ONE query.

    Models whose module has been uninstalled still leave mail.followers rows
    behind but have no ir.model record; they are simply absent from the maps
    and the caller falls back to the technical name.
    """
    labels, model_ids = {}, {}
    names = [name for name in model_names if name]
    if names:
        for row in env['ir.model'].search_read([('model', 'in', names)], ['model', 'name']):
            labels[row['model']] = row['name']
            model_ids[row['model']] = row['id']
    return labels, model_ids


def _internal_user_by_partner(env, partner_ids):
    """{partner_id: user_id} for partners owning an internal user, in ONE query.

    Archived users count: an inactive employee still explains historical
    follower rows. Portal/public users are ``share`` users and are deliberately
    excluded, so they are reported as plain contacts.
    """
    result = {}
    ids = [pid for pid in partner_ids if pid]
    if ids:
        rows = env['res.users'].with_context(active_test=False).search_read(
            [('partner_id', 'in', ids), ('share', '=', False)], ['partner_id'])
        for row in rows:
            partner = row.get('partner_id')
            if partner and partner[0] not in result:
                result[partner[0]] = row['id']
    return result


def _follower_groups(env, groupby, domain=None, limit=None):
    """One grouped, ranked, LIMITed query over mail.followers, as the current user.

    ``lazy=False`` groups by every key at once. Ordering and truncation stay in
    SQL: ranking in Python would mean materialising one dict per group first,
    which is one dict per followed record on the record report.

    Rows without a partner are excluded - 14.0 kept channel followers in this
    table, and a channel subscription notifies no single person.
    """
    full_domain = [('partner_id', '!=', False)] + list(domain or [])
    groups = env['mail.followers'].read_group(
        full_domain, [COUNT_SPEC], groupby, lazy=False,
        orderby='%s desc' % COUNT_ALIAS, limit=limit or None)
    for group in groups:
        # keep one stable key whatever the series names the aggregate
        group[COUNT_ALIAS] = group.get(COUNT_ALIAS) or group.get('__count') or 0
    return groups


def _ranked_groups(env, groupby, limit, domain=None):
    """Top ``limit`` groups plus a flag telling whether more were left out."""
    groups = _follower_groups(env, groupby, domain=domain,
                              limit=(limit + 1) if limit else None)
    truncated = bool(limit) and len(groups) > limit
    return (groups[:limit] if truncated else groups), truncated


def _truncation_suffix(kept):
    return ' (%s)' % _('top %s', kept)


class FollowersAuditPartner(models.TransientModel):
    """One line per follower and document type: who follows how much, of what."""
    _name = 'followers.audit.partner'
    _description = 'Followers Audit: Followers by Person'
    _order = 'partner_total desc, partner_name, follow_count desc, model_label'
    _rec_name = 'partner_name'

    partner_id = fields.Many2one(
        'res.partner', string='Follower', readonly=True, index=True, ondelete='cascade',
        help='The contact subscribed to the records counted on this line.')
    partner_name = fields.Char(string='Follower Name', readonly=True)
    user_id = fields.Many2one(
        'res.users', string='User Account', readonly=True, ondelete='cascade',
        help='The internal user account owned by this contact, when there is one. '
             'Empty for contacts that only exist in the address book.')
    follower_type = fields.Selection(
        [('internal', 'Internal User'), ('contact', 'Contact')],
        string='Follower Type', readonly=True,
        help='Internal User: the contact owns a non-portal user account, so these '
             'subscriptions produce in-app and e-mail notifications for a colleague. '
             'Contact: an address-book contact or a portal user.')
    res_model = fields.Char(
        string='Model', readonly=True,
        help='Technical model name stored on the follower row.')
    model_id = fields.Many2one(
        'ir.model', string='Document Type', readonly=True, ondelete='cascade',
        help='Empty when the follower rows point at a model whose module is no '
             'longer installed.')
    model_label = fields.Char(string='Document', readonly=True)
    follow_count = fields.Integer(
        string='Records Followed', readonly=True,
        help='Number of records of this document type followed by this contact.')
    partner_total = fields.Integer(
        string='Total Records Followed', readonly=True,
        help='Number of records this contact follows across every document type.',
        **NO_AGGREGATE)

    @api.model
    def _fa_build(self):
        """Materialise the report. Returns (lines, followers_kept, truncated)."""
        limit = _line_limit(self.env)
        # 1. rank the followers themselves - bounded and ordered by the database
        top, truncated = _ranked_groups(self.env, ['partner_id'], limit)
        totals, names = {}, {}
        for group in top:
            partner = group.get('partner_id')
            if partner:
                totals[partner[0]] = group[COUNT_ALIAS]
                names[partner[0]] = partner[1] or ''
        if not totals:
            return self.browse(), 0, False

        # 2. split exactly those followers over the document types they follow,
        #    so every line's partner_total is the true sum of that person's
        #    counts. Bounded by (followers kept x models a person follows).
        rows = [
            (group['partner_id'][0], group.get('res_model') or '', group[COUNT_ALIAS])
            for group in _follower_groups(self.env, ['partner_id', 'res_model'],
                                          domain=[('partner_id', 'in', list(totals))])
            if group.get('partner_id')
        ]
        # heaviest follower first, then their own biggest document type
        rows.sort(key=lambda row: (-totals.get(row[0], 0),
                                   (names.get(row[0]) or '').lower(), -row[2], row[1]))

        labels, model_ids = _model_labels(self.env, {row[1] for row in rows})
        users = _internal_user_by_partner(self.env, totals)

        vals_list = []
        for partner_id, res_model, count in rows:
            user_id = users.get(partner_id)
            vals_list.append({
                'partner_id': partner_id,
                'partner_name': names.get(partner_id) or '',
                'user_id': user_id or False,
                'follower_type': 'internal' if user_id else 'contact',
                'res_model': res_model,
                'model_id': model_ids.get(res_model, False),
                'model_label': labels.get(res_model) or res_model or _('Unknown model'),
                'follow_count': count,
                'partner_total': totals.get(partner_id, 0),
            })
        lines = self.create(vals_list) if vals_list else self.browse()
        return lines, len(totals), truncated

    @api.model
    def action_open_followers_by_person(self):
        lines, kept, truncated = self._fa_build()
        name = _('Followers by Person')
        if truncated:
            name += _truncation_suffix(kept)
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': self._name,
            'view_mode': '%s,form' % LIST_MODE,
            'domain': [('id', 'in', lines.ids)],
            'search_view_id': [
                self.env.ref('followers_audit_report.view_followers_audit_partner_search').id,
                'search',
            ],
            'context': {'create': False, 'edit': False, 'delete': False},
            'target': 'current',
            'help': '<p class="o_view_nocontent_smiling_face">%s</p><p>%s</p>' % (
                _('Nobody follows anything yet'),
                _('This report counts subscriptions only. To unsubscribe someone, '
                  'open the record and use the Followers button in its chatter.'),
            ),
        }

    def action_open_followed_records(self):
        """Open the followed records themselves, in their own standard view.

        Deliberately not a follower-row list: the record form carries the
        chatter, which is where Odoo lets you remove a follower.
        """
        self.ensure_one()
        if not self.partner_id or not self.res_model:
            raise UserError(_('This line does not point at a document type.'))
        if self.res_model not in self.env:
            raise UserError(_(
                'The model "%s" is not installed in this database anymore, so its '
                'records cannot be opened.', self.res_model))
        model = self.env[self.res_model]
        if model._abstract or model._transient:
            raise UserError(_('"%s" does not store records that can be opened.',
                              self.model_label))
        # Bounded like the report itself: a heavy follower is exactly what this
        # report finds, and its id list would otherwise be shipped to the browser.
        limit = _line_limit(self.env)
        rows = self.env['mail.followers'].search_read(
            [('res_model', '=', self.res_model), ('partner_id', '=', self.partner_id.id)],
            ['res_id'], limit=limit or None)
        res_ids = [row['res_id'] for row in rows if row.get('res_id')]
        name = _('%(document)s followed by %(follower)s', **{
            'document': self.model_label or self.res_model,
            'follower': self.partner_name or (self.partner_id.display_name or ''),
        })
        if limit and len(res_ids) >= limit and self.follow_count > len(res_ids):
            name += _truncation_suffix(len(res_ids))
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': self.res_model,
            'view_mode': '%s,form' % LIST_MODE,
            'domain': [('id', 'in', res_ids)],
            'target': 'current',
        }


class FollowersAuditRecord(models.TransientModel):
    """One line per followed record: which documents notify the most people."""
    _name = 'followers.audit.record'
    _description = 'Followers Audit: Records by Follower Count'
    _order = 'follower_count desc, model_label, res_id'
    _rec_name = 'record_label'

    res_model = fields.Char(
        string='Model', readonly=True,
        help='Technical model name stored on the follower rows.')
    model_id = fields.Many2one(
        'ir.model', string='Document Type', readonly=True, ondelete='cascade',
        help='Empty when the follower rows point at a model whose module is no '
             'longer installed.')
    model_label = fields.Char(string='Document', readonly=True)
    res_id = fields.Integer(string='Record ID', readonly=True, **NO_AGGREGATE)
    record_label = fields.Char(string='Record', readonly=True)
    record_available = fields.Boolean(
        string='Record Exists', readonly=True,
        help='Unticked when the follower rows outlived the record they point at, '
             'or when your access rights do not let you read it. Those rows are '
             'reported, never deleted.')
    follower_count = fields.Integer(
        string='Followers', readonly=True,
        help='Number of contacts subscribed to this record. Counted from the '
             'follower rows themselves, so records you may not read are counted too.')

    @api.model
    def _fa_resolve_records(self, ids_by_model):
        """Bulk-resolve record labels: batched per model, never per record.

        ``search`` is used rather than ``browse().exists()`` on purpose. Only
        search applies record rules: browse+exists is a bare SELECT id, and the
        display_name read that follows would then raise AccessError for the
        whole batch as soon as ONE record is out of the reader's scope, blanking
        every label of that model. base.group_system is not the superuser, so
        that case is the norm on multi-company databases.

        Each model is also isolated in its own savepoint - a third-party
        _compute_display_name can still fail - and results are published only
        once the block succeeded, so a failure never leaves half a model's
        records flagged as available.
        """
        existing, labels = {}, {}
        for res_model, res_ids in ids_by_model.items():
            if not res_model or res_model not in self.env:
                continue
            model = self.env[res_model]
            if model._abstract or model._transient:
                continue
            try:
                with self.env.cr.savepoint():
                    # active_test=False or archived records look "deleted"
                    readable = model.with_context(active_test=False).search(
                        [('id', 'in', res_ids)])
                    found = set(readable.ids)
                    names = {}
                    for record in readable:  # display_name prefetched for the set
                        names[(res_model, record.id)] = record.display_name
                    existing[res_model] = found
                    labels.update(names)
            except Exception:  # pylint: disable=broad-except
                _logger.warning(
                    'Followers Audit: could not resolve record names for model %s',
                    res_model, exc_info=True)
        return existing, labels

    @api.model
    def _fa_build(self):
        """Materialise the report. Returns (lines, records_kept, truncated)."""
        limit = _line_limit(self.env)
        groups, truncated = _ranked_groups(self.env, ['res_model', 'res_id'], limit)
        # already ranked by the database: keep that order
        raw = [(group.get('res_model') or '', group.get('res_id') or 0,
                group[COUNT_ALIAS]) for group in groups]

        model_labels, model_ids = _model_labels(self.env, {row[0] for row in raw})
        ids_by_model = defaultdict(list)
        for res_model, res_id, _count in raw:
            ids_by_model[res_model].append(res_id)
        existing, record_labels = self._fa_resolve_records(ids_by_model)

        vals_list = []
        for res_model, res_id, count in raw:
            model_label = model_labels.get(res_model) or res_model or _('Unknown model')
            vals_list.append({
                'res_model': res_model,
                'model_id': model_ids.get(res_model, False),
                'model_label': model_label,
                'res_id': res_id,
                'record_label': record_labels.get((res_model, res_id))
                or '%s #%s' % (model_label, res_id),
                'record_available': res_id in existing.get(res_model, ()),
                'follower_count': count,
            })
        lines = self.create(vals_list) if vals_list else self.browse()
        return lines, len(raw), truncated

    @api.model
    def action_open_records_by_followers(self):
        lines, kept, truncated = self._fa_build()
        name = _('Records by Follower Count')
        if truncated:
            name += _truncation_suffix(kept)
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': self._name,
            'view_mode': '%s,form' % LIST_MODE,
            'domain': [('id', 'in', lines.ids)],
            'search_view_id': [
                self.env.ref('followers_audit_report.view_followers_audit_record_search').id,
                'search',
            ],
            'context': {'create': False, 'edit': False, 'delete': False},
            'target': 'current',
            'help': '<p class="o_view_nocontent_smiling_face">%s</p><p>%s</p>' % (
                _('No record has followers yet'),
                _('This report counts subscriptions only. To unsubscribe someone, '
                  'open the record and use the Followers button in its chatter.'),
            ),
        }

    def action_open_record(self):
        """Open the underlying record, where the chatter manages its followers."""
        self.ensure_one()
        if not self.res_model or self.res_model not in self.env:
            raise UserError(_(
                'The model "%s" is not installed in this database anymore, so this '
                'record cannot be opened.', self.res_model or ''))
        if not self.record_available:
            raise UserError(_(
                'This record no longer exists, or your access rights do not let you '
                'read it. Its follower rows are reported here, never deleted.'))
        return {
            'type': 'ir.actions.act_window',
            'name': self.record_label or self.model_label,
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
