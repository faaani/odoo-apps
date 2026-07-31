# -*- coding: utf-8 -*-
# Part of field_rules_by_group. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from lxml import etree

from odoo import _, api, models, SUPERUSER_ID
from odoo.exceptions import AccessError

FLAGS = ('readonly', 'invisible', 'required')


class Base(models.AbstractModel):
    _inherit = 'base'

    def _field_group_rules(self):
        """Active field rules that apply to the current user on this model.

        Returns a (possibly empty) tuple of plain dicts. Must stay cheap for
        the common case of a model without rules: one ormcached lookup, no
        query. Superuser, sudo() flows and (by default) system administrators
        are exempt so that system automation and data repair always work.
        """
        env = self.env
        if self._abstract or self._transient or self._name == 'field.group.rule':
            return ()
        if env.su or env.uid == SUPERUSER_ID:
            return ()
        if 'field.group.rule' not in env:
            return ()  # registry still loading this module
        rules = env['field.group.rule']._get_rules(self._name)
        if not rules:
            return ()
        user = env.user
        is_admin = user.has_group('base.group_system')
        if 'all_group_ids' in user._fields:
            # 19.0: groups_id was renamed group_ids and no longer contains
            # the implied groups; all_group_ids does.
            user_groups = set(user.all_group_ids.ids)
        else:
            user_groups = set(user.groups_id.ids)
        matching = []
        for rule in rules:
            if is_admin and not rule['apply_to_admin']:
                continue
            if rule['groups'] and not user_groups.intersection(rule['groups']):
                continue
            matching.append(rule)
        return tuple(matching)

    @api.model
    def _field_group_rules_stamp(self, arch, rules):
        """Stamp readonly/invisible/required on the matching form fields.

        Returns the patched arch string, or None when nothing matched.
        """
        flags_by_field = {}
        for rule in rules:
            merged = flags_by_field.setdefault(
                rule['field'], dict.fromkeys(FLAGS, False))
            for flag in FLAGS:
                merged[flag] = merged[flag] or rule[flag]
        doc = etree.fromstring(arch)
        changed = False
        for node in doc.iter('field'):
            flags = flags_by_field.get(node.get('name'))
            if not flags:
                continue
            # fields nested under another <field> belong to an embedded
            # sub-view of a different model: never stamp those
            parent = node.getparent()
            while parent is not None and parent.tag != 'field':
                parent = parent.getparent()
            if parent is not None:
                continue
            if flags['invisible'] and flags['required']:
                # two separate rules merged into an unfillable field:
                # invisible wins, otherwise the form could never be saved
                flags = dict(flags, required=False)
            for flag in FLAGS:
                if flags[flag]:
                    node.set(flag, '1')
                    changed = True
        return etree.tostring(doc, encoding='unicode') if changed else None

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super(Base, self).get_view(view_id, view_type, **options)
        if view_type != 'form':
            return res
        rules = self._field_group_rules()
        if not rules:
            return res
        arch = self._field_group_rules_stamp(res['arch'], rules)
        if arch is not None:
            res = dict(res)  # never mutate a dict super might share
            res['arch'] = arch
        return res

    def _field_group_rules_check_vals(self, vals_list):
        """Server-side enforcement of read-only rules (RPC-proof).

        Invisible and required are form-level concerns and are deliberately
        not enforced here (documented limitation).
        """
        rules = self._field_group_rules()
        if not rules:
            return
        readonly_rules = {r['field']: r for r in rules if r['readonly']}
        if not readonly_rules:
            return
        for vals in vals_list:
            if not isinstance(vals, dict):
                continue
            for field_name in vals:
                rule = readonly_rules.get(field_name)
                if rule:
                    raise AccessError(_(
                        'The field "%(field)s" on %(model)s is read-only for '
                        'you (field rule: %(rule)s). Ask an administrator to '
                        'change it or to adjust the rule.'
                    ) % {'field': field_name,
                         'model': self._description or self._name,
                         'rule': rule['name']})

    @api.model_create_multi
    def create(self, vals_list):
        self._field_group_rules_check_vals(vals_list)
        return super(Base, self).create(vals_list)

    def write(self, vals):
        self._field_group_rules_check_vals([vals])
        return super(Base, self).write(vals)
