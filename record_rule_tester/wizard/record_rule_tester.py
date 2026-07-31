# -*- coding: utf-8 -*-
# Part of record_rule_tester. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

# A count is always taken with a LIMIT: "how many orders can this user see?"
# must stay a cheap question even on a table with millions of rows. The wizard
# shows the cap and flags a count that reached it, so a capped figure is never
# read as an exact one.
DEFAULT_COUNT_LIMIT = 10000
MAX_COUNT_LIMIT = 200000

OPERATIONS = (
    ('read', 'Read'),
    ('write', 'Write'),
    ('create', 'Create'),
    ('unlink', 'Delete'),
)
OPERATION_SEQUENCE = {'read': 10, 'write': 20, 'create': 30, 'unlink': 40}


def model_has_permission(model, operation):
    """Model-level access (ir.model.access) for ``model``'s user, as a boolean.

    18.0 replaced ``check_access_rights`` with ``has_access``; on an empty
    recordset both answer the same question: may this user perform *operation*
    on the model at all, record rules aside.
    """
    if hasattr(model, 'has_access'):  # 18.0+
        return model.has_access(operation)
    return model.check_access_rights(operation, raise_exception=False)


def user_groups(user):
    """Every group ``user`` belongs to, implied groups included.

    14.0-18.0 flatten implied groups into ``groups_id`` when the user is saved;
    19.0 splits the direct links (``group_ids``) from the transitive closure
    (``all_group_ids``), so the closure is preferred when it exists.
    """
    for fname in ('all_group_ids', 'groups_id', 'group_ids'):
        if fname in user._fields:
            return user[fname]
    return user.env['res.groups'].browse()


class RecordRuleTester(models.TransientModel):
    _name = 'record.rule.tester'
    _description = 'Record Rule Tester'

    # _rec_name falls back to this field, so the breadcrumb reads
    # "Marie Duval on res.partner" instead of "record.rule.tester,1"
    name = fields.Char(string='Test', compute='_compute_name')

    user_id = fields.Many2one(
        'res.users', string='User', required=True, ondelete='cascade',
        default=lambda self: self.env.user,
        help='The user whose access is being tested. Nothing is ever done in '
             'this user name: the tester only runs read-only searches as them.',
    )
    model_id = fields.Many2one(
        'ir.model', string='Model', required=True, ondelete='cascade',
        help='The model to test, for example Sales Order (sale.order).',
    )
    model_name = fields.Char(
        related='model_id.model', string='Technical Model', readonly=True)
    record_id = fields.Integer(
        string='Record ID',
        help='Optional. The database id of one specific record. Leave it at 0 '
             'to test the model only; fill it in to get a verdict on whether '
             'this user can read that exact record, and which rule hides it.',
    )
    count_limit = fields.Integer(
        string='Count Cap', required=True, default=DEFAULT_COUNT_LIMIT,
        help='Counts stop at this many records so that testing a huge model '
             'stays fast. A count that reached the cap is flagged as capped.',
    )

    state = fields.Selection(
        [('draft', 'Not Run'), ('done', 'Done')],
        string='Status', default='draft', readonly=True)

    # ------------------------------------------------------------- results ---
    access_state = fields.Selection(
        [('unknown', 'Not run'), ('ok', 'Has access'), ('no_access', 'No access')],
        string='Model Access', default='unknown', readonly=True,
        help='Whether an access control line grants this user read on the '
             'model. Without one, record rules never even get a say.',
    )
    access_message = fields.Text(string='Access Summary', readonly=True)
    readable_count = fields.Integer(
        string='Readable Records', readonly=True,
        help='How many records of this model the user can read, obtained by '
             'running the search as that user.',
    )
    reference_count = fields.Integer(
        string='Your Own Readable Records', readonly=True,
        help='How many records YOU, the administrator running this test, can '
             'read - same model, same cap, and likewise with every company you '
             'are allowed to access enabled. It is a comparison figure, not a '
             'database total: your own record rules apply to it too.',
    )
    counts_capped = fields.Boolean(
        string='Counts Capped', readonly=True,
        help='Ticked when at least one count stopped at the cap, so the real '
             'number is that value or more.',
    )
    company_names = fields.Char(
        string='Companies Used', readonly=True,
        help='The companies enabled while evaluating, which is every company '
             'the tested user is allowed to access. Multi-company record rules '
             'are evaluated against exactly these.',
    )
    global_rule_count = fields.Integer(string='Global Rules', readonly=True)
    group_rule_count = fields.Integer(string='Group Rules', readonly=True)

    record_verdict = fields.Selection(
        [('not_tested', 'No record tested'),
         ('allowed', 'Can read this record'),
         ('denied', 'Cannot read this record'),
         ('missing', 'No such record'),
         ('no_access', 'No access to this model')],
        string='Verdict', default='not_tested', readonly=True)
    record_message = fields.Text(string='Verdict Detail', readonly=True)
    warning = fields.Text(string='Notes', readonly=True)

    op_ids = fields.One2many(
        'record.rule.tester.op', 'tester_id', string='Operations', readonly=True)
    rule_ids = fields.One2many(
        'record.rule.tester.rule', 'tester_id', string='Applicable Rules',
        readonly=True)

    @api.depends('user_id', 'model_id')
    def _compute_name(self):
        for tester in self:
            if tester.user_id and tester.model_id:
                tester.name = _('%(user)s on %(model)s',
                                user=tester.user_id.display_name,
                                model=tester.model_id.model)
            else:
                tester.name = _('Record Rule Tester')

    @api.constrains('count_limit')
    def _check_count_limit(self):
        for tester in self:
            if not 1 <= tester.count_limit <= MAX_COUNT_LIMIT:
                raise ValidationError(_(
                    'The count cap must be between 1 and %s.', MAX_COUNT_LIMIT))

    # ------------------------------------------------------------- helpers ---
    def _check_operator(self):
        """Only a Settings administrator may ask about somebody else's access.

        security/ir.model.access.csv already restricts the three models to
        base.group_system; this is the second lock, on the method itself.
        """
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_(
                'The Record Rule Tester is reserved to Settings administrators.'))

    def _target_context(self):
        """Context to evaluate the tested user's access in.

        Everything that would leak the operator's own session into the tested
        user's evaluation is dropped. ``allowed_company_ids`` above all: left
        in, the counts would be taken in the operator's companies, and reading
        it as another user raises "Access to unauthorized or invalid
        companies". Without it Odoo falls back on the tested user's own
        companies, which is what we want. ``active_test`` is forced off so an
        archived record is never mistaken for a record a rule hides.
        """
        dropped = ('allowed_company_ids', 'active_test', 'active_id',
                   'active_ids', 'active_model', 'params')
        ctx = {
            key: value for key, value in self.env.context.items()
            if key not in dropped
            and not key.startswith('default_')
            and not key.startswith('search_default_')
        }
        ctx['active_test'] = False
        return ctx

    def _target_model(self):
        """The model to test, checked to be something that holds records."""
        model_name = self.model_id.model
        if model_name not in self.env:
            raise UserError(_(
                'The model %s is not in this database registry: the module '
                'defining it is probably not installed.', model_name))
        model = self.env[model_name]
        if model._abstract:
            raise UserError(_(
                '%s is an abstract model. It stores no records, so there is '
                'nothing to count or to test.', model_name))
        return model

    def _capped_count(self, model, domain, cap):
        """Records matching ``domain``, never walking past ``cap``.

        ``search_count(limit=...)`` only exists from 16.0, so the LIMIT goes on
        the search itself - one query either way.
        """
        return len(model.search(domain, limit=cap))

    def _collect_notes(self, model, user, cap):
        notes = []
        if user.id == SUPERUSER_ID:
            notes.append(str(_(
                '%s is the superuser: it bypasses every access right and every '
                'record rule, so these figures are not a meaningful '
                'restriction test. Test a real user instead.',
                user.display_name)))
        if not user.active:
            notes.append(str(_('This user is archived and cannot log in.')))
        if getattr(model, '_transient', False):
            notes.append(str(_(
                '%s is a wizard (transient) model. Its records are short-lived '
                'and deleted by the vacuum job.', model._name)))
        if model._inherits:
            notes.append(str(_(
                '%(model)s delegates to %(parents)s through _inherits. Odoo '
                'also applies the record rules of those parent models, and '
                'this screen lists only the rules defined on %(model)s - run '
                'the test again on a parent model to see them.',
                model=model._name, parents=', '.join(sorted(model._inherits)))))
        notes.append(str(_(
            'Rule domains are listed exactly as stored, so expressions such as '
            'user.company_id are not expanded. What matters is the evaluated '
            'result: the counts and the verdict are produced by really running '
            'the searches as %s.', user.display_name)))
        notes.append(str(_(
            'Counts stop at %s records, and archived records are included.',
            cap)))
        return notes

    # ---------------------------------------------------------- evaluation ---
    def _evaluate_operation(self, target, rule_env, model_name, operation, cap):
        """One operation, as a dict. Never raises: a denied model is a result.

        Every evaluation runs inside a savepoint so that a refused query, or a
        record rule whose domain is broken, leaves the cursor usable.
        """
        result = {
            'operation': operation,
            'sequence': OPERATION_SEQUENCE[operation],
            'acl_allowed': False,
            'rule_count': 0,
            'countable': operation != 'create',
            'record_count': 0,
            'capped': False,
            'note': '',
        }
        try:
            with self.env.cr.savepoint():
                result['acl_allowed'] = model_has_permission(target, operation)
                result['rule_count'] = len(
                    rule_env._get_rules(model_name, mode=operation))
        except AccessError as error:
            result['countable'] = False
            result['note'] = str(_('No access: %s', error))
            return result

        if not result['acl_allowed']:
            result['countable'] = False
            result['note'] = str(_(
                'No access control line grants this operation on %s, so the '
                'user cannot perform it on any record and the record rules '
                'below never apply to it.', model_name))
            return result

        if operation == 'create':
            result['note'] = str(_(
                'Create rules are checked against the values of a NEW record, '
                'so there is no set of existing records to count.'))
            return result

        try:
            with self.env.cr.savepoint():
                domain = []
                if operation != 'read':
                    # Odoo's own rule engine, asked for this user and this
                    # operation. The search below applies the read rules on top
                    # of it, so the figure is "records the user can both see
                    # and write/delete".
                    domain = rule_env._compute_domain(model_name, mode=operation)
                    if domain is None:
                        domain = []
                result['record_count'] = self._capped_count(target, domain, cap)
        except AccessError as error:
            result['countable'] = False
            result['note'] = str(_('No access: %s', error))
            return result
        except Exception as error:  # pylint: disable=broad-except
            # A record rule domain is administrator-authored Python evaluated
            # by safe_eval; a broken one can raise almost anything. Surfacing
            # that is the whole point of this tool, so it must not escape as a
            # red traceback in the client.
            _logger.warning(
                'record_rule_tester: %s count failed on %s: %s',
                operation, model_name, error)
            result['countable'] = False
            result['note'] = str(_(
                'The count could not be taken: %s. This usually means a record '
                'rule on this model has an invalid domain.', error))
            return result

        result['capped'] = result['record_count'] >= cap
        if result['capped']:
            result['note'] = str(_(
                'Capped: there are %s or more such records.', cap))
        elif operation != 'read':
            result['note'] = str(_(
                'Records the user can both see and %s.', operation))
        return result

    def _evaluate_record(self, target, rule_env, model):
        """Verdict on one record id, plus the ids of the rules that hide it."""
        model_name = model._name
        record_id = self.record_id
        if record_id <= 0:
            return {
                'record_verdict': 'not_tested',
                'record_message': str(_(
                    'Fill in a Record ID to get a verdict on one specific '
                    'record.')),
            }, []
        # exists() is a plain SELECT on the table: it answers "is there such a
        # row" without consulting access rights, which is exactly what tells
        # "no such record" apart from "the user cannot see it".
        if not model.browse(record_id).exists():
            return {
                'record_verdict': 'missing',
                'record_message': str(_(
                    'There is no %(model)s with id %(record)s in the database, '
                    'so no record rule is involved.',
                    model=model_name, record=record_id)),
            }, []

        try:
            with self.env.cr.savepoint():
                if not model_has_permission(target, 'read'):
                    return {
                        'record_verdict': 'no_access',
                        'record_message': str(_(
                            'No access control line grants read on %s to this '
                            'user. Record rules are not the reason - the model '
                            'itself is out of reach.', model_name)),
                    }, []
                found = target.search([('id', '=', record_id)], limit=1)
        except AccessError as error:
            return {
                'record_verdict': 'no_access',
                'record_message': str(_('No access: %s', error)),
            }, []

        if found:
            return {
                'record_verdict': 'allowed',
                'record_message': str(_(
                    '%(user)s can read %(model)s #%(record)s: the record '
                    'satisfies every record rule that applies to them.',
                    user=self.user_id.display_name, model=model_name,
                    record=record_id)),
            }, []

        failing = self.env['ir.rule'].browse()
        try:
            with self.env.cr.savepoint():
                # _get_failing is Odoo's own blame routine - the one that names
                # rules in the AccessError messages the server raises.
                failing = rule_env._get_failing(
                    target.browse(record_id), mode='read')
                failing = self.env['ir.rule'].browse(failing.ids)
        except Exception as error:  # pylint: disable=broad-except
            _logger.warning(
                'record_rule_tester: could not attribute the denial on %s#%s: %s',
                model_name, record_id, error)

        lines = [str(_(
            '%(user)s cannot read %(model)s #%(record)s.',
            user=self.user_id.display_name, model=model_name,
            record=record_id))]
        global_failing = failing.filtered(lambda rule: not rule.groups)
        group_failing = failing - global_failing
        if global_failing:
            lines.append(str(_(
                'Excluded by the global rule(s): %s. A global rule is ANDed '
                'with every other rule, so a single one that does not match is '
                'enough to hide the record.',
                ', '.join(global_failing.mapped('name')))))
        if group_failing:
            lines.append(str(_(
                'None of the group rules that apply to this user matched: %s. '
                'Group rules are ORed, so the record stays hidden until at '
                'least one of them matches.',
                ', '.join(group_failing.mapped('name')))))
        if not failing:
            lines.append(str(_(
                'Odoo reports no failing rule on %s itself. The record is '
                'filtered out for another reason - most often a rule on a '
                'parent model reached through _inherits, or a company this '
                'user is not allowed to access.', model_name)))
        return {
            'record_verdict': 'denied',
            'record_message': '\n'.join(lines),
        }, failing.ids

    def _build_rule_values(self, rule_env, model_name, user):
        """One line per record rule Odoo would apply to this user and model."""
        rule_ids = []
        for operation, _label in OPERATIONS:
            # _get_rules is Odoo's own selector: the model, the operation, the
            # user's groups and the active flag are all handled by it.
            rule_ids.extend(rule_env._get_rules(model_name, mode=operation).ids)
        # re-browse as the operator: these lines are displayed to them, not to
        # the tested user
        rules = self.env['ir.rule'].browse(sorted(set(rule_ids)))
        groups_of_user = user_groups(user)
        values = []
        for rule in rules:
            is_global = not rule.groups
            matching = rule.groups & groups_of_user
            values.append({
                'tester_id': self.id,
                'sequence': 10 if is_global else 20,
                'rule_id': rule.id,
                'rule_name': rule.name,
                'kind': 'global' if is_global else 'group',
                'domain_force': rule.domain_force or '[]',
                'group_names': ', '.join(matching.mapped('display_name')),
                'perm_read': rule.perm_read,
                'perm_write': rule.perm_write,
                'perm_create': rule.perm_create,
                'perm_unlink': rule.perm_unlink,
            })
        return values

    # -------------------------------------------------------------- action ---
    def action_run(self):
        """Evaluate the tested user's access and fill the result section in."""
        self.ensure_one()
        self._check_operator()
        model = self._target_model()
        model_name = model._name
        user = self.user_id
        cap = self.count_limit
        context = self._target_context()
        # The environment is built directly rather than through
        # with_user().with_context(): with_context() deliberately RE-INJECTS
        # allowed_company_ids when the replacement context does not carry it,
        # so it cannot be used to drop the operator's company switcher. Left in
        # place, Odoo raises "Access to unauthorized or invalid companies" the
        # moment a rule domain is evaluated for a user who is not allowed into
        # those companies.
        target_env = self.env(user=user.id, context=context, su=False)
        target = target_env[model_name]
        rule_env = target_env['ir.rule']

        self.op_ids.unlink()
        self.rule_ids.unlink()

        rule_values = self._build_rule_values(rule_env, model_name, user)
        op_results = [
            self._evaluate_operation(target, rule_env, model_name, operation, cap)
            for operation, _label in OPERATIONS
        ]
        verdict, blocking_rule_ids = self._evaluate_record(
            target, rule_env, model)
        read_result = op_results[0]

        try:
            with self.env.cr.savepoint():
                company_ids = target.env.companies.ids
        except AccessError:
            company_ids = []

        own_count = 0
        try:
            with self.env.cr.savepoint():
                own_count = self._capped_count(
                    self.env(context=context)[model_name], [], cap)
        except AccessError:
            own_count = 0

        if read_result['acl_allowed']:
            access_state = 'ok'
            access_message = str(_(
                '%(user)s may read %(model)s and can see %(count)s of its '
                'records (cap %(cap)s).',
                user=user.display_name, model=model_name,
                count=read_result['record_count'], cap=cap))
        else:
            access_state = 'no_access'
            access_message = str(_(
                '%(user)s has no access control line granting read on '
                '%(model)s. The model is out of reach whatever the record '
                'rules say.', user=user.display_name, model=model_name))

        for values in rule_values:
            values['blocks_record'] = values['rule_id'] in blocking_rule_ids
        self.env['record.rule.tester.rule'].create(rule_values)
        self.env['record.rule.tester.op'].create(
            [dict(result, tester_id=self.id) for result in op_results])

        global_rules = sum(1 for v in rule_values if v['kind'] == 'global')
        write_values = {
            'state': 'done',
            'access_state': access_state,
            'access_message': access_message,
            'readable_count': read_result['record_count'],
            'reference_count': own_count,
            'counts_capped': any(result['capped'] for result in op_results),
            'company_names': ', '.join(
                self.env['res.company'].browse(company_ids).mapped('display_name')),
            'global_rule_count': global_rules,
            'group_rule_count': len(rule_values) - global_rules,
            'warning': '\n'.join(self._collect_notes(model, user, cap)),
        }
        write_values.update(verdict)
        self.write(write_values)
        return False


class RecordRuleTesterOp(models.TransientModel):
    _name = 'record.rule.tester.op'
    _description = 'Record Rule Tester Operation Result'
    _order = 'sequence, id'

    tester_id = fields.Many2one(
        'record.rule.tester', string='Test', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    operation = fields.Selection(
        list(OPERATIONS), string='Operation', required=True)
    acl_allowed = fields.Boolean(
        string='Model Access',
        help='Ticked when an access control line grants this operation on the '
             'model. Without it the operation is refused before record rules '
             'are consulted at all.')
    rule_count = fields.Integer(
        string='Rules',
        help='How many record rules Odoo applies to this user for this '
             'operation on this model.')
    countable = fields.Boolean(
        string='Counted',
        help='Unticked when no count is possible: model access is denied, or '
             'the operation is Create, which validates new values instead of '
             'filtering existing records.')
    record_count = fields.Integer(
        string='Records',
        help='How many existing records the operation may be performed on, '
             'obtained by running the search as the tested user.')
    capped = fields.Boolean(
        string='Capped',
        help='Ticked when the count stopped at the cap: the real number is '
             'that value or more.')
    note = fields.Char(string='Note')


class RecordRuleTesterRule(models.TransientModel):
    _name = 'record.rule.tester.rule'
    _description = 'Record Rule Tester Applicable Rule'
    _order = 'sequence, rule_name, id'

    tester_id = fields.Many2one(
        'record.rule.tester', string='Test', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    rule_id = fields.Many2one('ir.rule', string='Record Rule', ondelete='cascade')
    rule_name = fields.Char(string='Rule')
    kind = fields.Selection(
        [('global', 'Global'), ('group', 'Group')], string='Kind',
        help='Global rules carry no group: Odoo applies them to everybody and '
             'ANDs them together, so no group rule can widen them. Group rules '
             'are ORed with each other.')
    domain_force = fields.Text(
        string='Domain',
        help='The domain exactly as stored on the rule. Expressions such as '
             'user.company_id are NOT expanded here - what the user really '
             'ends up seeing is the evaluated result shown in the counts and '
             'in the verdict.')
    group_names = fields.Char(
        string='Through Groups',
        help="The tested user's groups this rule is attached to. Empty for a "
             'global rule, which applies to everybody.')
    blocks_record = fields.Boolean(
        string='Hides the Record',
        help='Ticked when this rule is one of those keeping the tested record '
             'out of reach, as reported by Odoo itself.')
    perm_read = fields.Boolean(string='Read')
    perm_write = fields.Boolean(string='Write')
    perm_create = fields.Boolean(string='Create')
    perm_unlink = fields.Boolean(string='Delete')
