# -*- coding: utf-8 -*-
# Part of record_owner_bulk_reassign. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

import psycopg2

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Responsible-user fields looked for on the active model, in order of preference.
# A candidate is only used when the model stores it and lets the user write it.
RESPONSIBLE_FIELDS = ('user_id', 'user_ids', 'activity_user_id')

# Hard cap on the number of records handled in one run (same figure as the
# sibling mass_field_update module). "All records of a user" can match tens of
# thousands of records; one unbounded run would exceed the worker time limit
# and roll back entirely. A capped run finishes, reports how many records are
# left, and a repeat run continues where it stopped.
MAX_RECORDS = 10000

# Fields that look like a responsible field but grant access instead of ownership:
# reassigning them would change who may log in where, not who is in charge.
ACCESS_CONTROL_FIELDS = frozenset([
    ('res.company', 'user_ids'),    # Accepted Users of a company
    ('res.groups', 'users'),
    ('res.groups', 'user_ids'),
])


class RecordOwnerReassignWizard(models.TransientModel):
    _name = 'record.owner.reassign.wizard'
    _description = 'Reassign Records in Bulk'

    res_model = fields.Char(string='Model', readonly=True)
    field_name = fields.Char(string='Responsible Field', readonly=True)
    field_label = fields.Char(string='Responsible', readonly=True)
    scope = fields.Selection(
        [('selection', 'Selected records'), ('user', 'All records of a user')],
        string='Apply To', default='selection', required=True)
    old_user_id = fields.Many2one('res.users', string='Current Owner')
    new_user_id = fields.Many2one(
        'res.users', string='New Owner', required=True,
        default=lambda self: self.env.user)
    log_note = fields.Boolean(
        string='Log a note in the chatter', default=True,
        help='Log a note on every reassigned record, so the change stays traceable.')
    selected_count = fields.Integer(string='Selected', readonly=True)
    record_count = fields.Integer(string='Records', compute='_compute_record_count')
    capped = fields.Boolean(
        string='Over the Batch Limit', compute='_compute_record_count',
        help='More records match than one run may process (%s).' % MAX_RECORDS)
    reassigned_count = fields.Integer(string='Reassigned', readonly=True)
    unchanged_count = fields.Integer(string='Already Assigned', readonly=True)
    skipped_count = fields.Integer(string='Skipped', readonly=True)
    failed_count = fields.Integer(string='Failed', readonly=True)
    remaining_count = fields.Integer(
        string='Remaining', readonly=True,
        help='Matching records left untouched by this run because of the '
             'batch limit; run the action again to continue.')

    # ------------------------------------------------------------------
    # Responsible-field detection
    # ------------------------------------------------------------------
    @api.model
    def _responsible_field(self, model_name, raise_if_missing=True):
        """Return the name of the writable responsible-user field of a model."""
        if not model_name or model_name not in self.env.registry:
            if raise_if_missing:
                raise UserError(
                    _('Open this action from the list or form view of the records '
                      'you want to reassign.'))
            return False
        model = self.env[model_name]
        for name in RESPONSIBLE_FIELDS:
            field = model._fields.get(name)
            if field is None or field.type not in ('many2one', 'many2many'):
                continue
            if field.comodel_name != 'res.users' or field.readonly or not field.store:
                continue
            if (model_name, name) in ACCESS_CONTROL_FIELDS:
                continue
            return name
        if raise_if_missing:
            raise UserError(
                _('"%(model)s" has no responsible user field that can be reassigned.\n'
                  'This action works on models carrying a stored, editable '
                  '"user_id", "user_ids" or "activity_user_id" field.',
                  model=model._description or model_name))
        return False

    @api.model
    def _context_record_ids(self):
        ids = list(self.env.context.get('active_ids') or [])
        if not ids and self.env.context.get('active_id'):
            ids = [self.env.context['active_id']]
        return ids

    @api.model
    def default_get(self, fields_list):
        res = super(RecordOwnerReassignWizard, self).default_get(fields_list)
        model_name = self.env.context.get('active_model')
        field_name = self._responsible_field(model_name)
        res.update(
            res_model=model_name,
            field_name=field_name,
            field_label=self.env[model_name]._fields[field_name].string,
            selected_count=len(self._context_record_ids()),
        )
        return res

    # ------------------------------------------------------------------
    # Target records
    # ------------------------------------------------------------------
    def _reassign_model(self):
        """The model to act on. The calling context wins over the stored value:
        readonly= is a UI-only flag, so res_model can be forged over RPC."""
        self.ensure_one()
        model_name = self.env.context.get('active_model') or self.res_model
        if not model_name or model_name not in self.env.registry:
            raise UserError(
                _('Open this action from the list or form view of the records '
                  'you want to reassign.'))
        return model_name

    def _owner_domain(self, field_name):
        self.ensure_one()
        return [(field_name, 'in', self.old_user_id.ids)]

    @api.depends('scope', 'old_user_id', 'res_model', 'selected_count')
    def _compute_record_count(self):
        for wizard in self:
            count = wizard.selected_count
            if wizard.scope == 'user':
                count = 0
                field_name = wizard._responsible_field(wizard.res_model, raise_if_missing=False)
                if field_name and wizard.old_user_id:
                    # search_count applies the user's own record rules; archived
                    # records count too, the action reassigns them as well
                    count = self.env[wizard.res_model].with_context(
                        active_test=False).search_count(wizard._owner_domain(field_name))
            wizard.record_count = count
            wizard.capped = count > MAX_RECORDS

    def _target_records(self, field_name):
        """Return ``(records, remaining)``: the records this run handles,
        capped at MAX_RECORDS, and how many matching records are left over
        for a repeat run. One unbounded run over a big owner would blow the
        worker time limit and roll back entirely; a capped run finishes and
        says exactly how much is left."""
        self.ensure_one()
        # active_test=False: a leaver's archived records must be handed over too
        model = self.env[self._reassign_model()].with_context(active_test=False)
        if self.scope == 'user':
            if not self.old_user_id:
                raise UserError(_('Choose the user whose records must be reassigned.'))
            domain = self._owner_domain(field_name)
            total = model.search_count(domain)
            records = model.search(domain, limit=MAX_RECORDS)
            return records, max(total - len(records), 0)
        ids = self._context_record_ids()
        if not ids:
            raise UserError(_('Select the records to reassign first.'))
        return model.browse(ids[:MAX_RECORDS]).exists(), max(len(ids) - MAX_RECORDS, 0)

    # ------------------------------------------------------------------
    # Reassignment
    # ------------------------------------------------------------------
    def _reassign_values(self, record, field):
        """Values to write on ``record``, or None when it is already assigned."""
        self.ensure_one()
        new_user = self.new_user_id
        current = record[field.name]
        if field.type == 'many2one':
            if current.id == new_user.id:
                return None
            return {field.name: new_user.id}
        # many2many: add the new owner and drop the previous one only, so the
        # other collaborators are never wiped (no (6, 0, ...) here, ever)
        old_user = self.old_user_id if self.old_user_id != new_user else self.env['res.users']
        commands = []
        if old_user and old_user in current:
            commands.append((3, old_user.id))
        if new_user not in current:
            commands.append((4, new_user.id))
        return {field.name: commands} if commands else None

    def _log_note(self, record, body):
        """Log the reassignment note; a chatter problem must not lose the write."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                record.message_post(body=body, subtype_xmlid='mail.mt_note')
        except Exception as err:  # noqa: BLE001 - e.g. an author without an email address
            _logger.warning('Could not log the reassignment note on %s(%s): %s',
                            record._name, record.id, err)

    def _note_body(self, record, field):
        self.ensure_one()
        previous = record[field.name]
        # str(): from 18.0 _() is lazy, and the note is stored/serialized right away
        return str(_(
            '%(field)s reassigned from %(old)s to %(new)s.',
            field=field.string,
            old=', '.join(previous.mapped('display_name')) or str(_('nobody')),
            new=self.new_user_id.display_name,
        ))

    def action_reassign(self):
        self.ensure_one()
        model_name = self._reassign_model()
        # always re-derive the field: a client may forge the readonly field_name
        field_name = self._responsible_field(model_name)
        if self.field_name and self.field_name != field_name:
            raise UserError(_('The responsible field cannot be changed.'))
        field = self.env[model_name]._fields[field_name]
        records, remaining = self._target_records(field_name)
        if not records:
            raise UserError(_('There is no record to reassign.'))

        reassigned = unchanged = skipped = failed = 0
        first_error = ''
        for record in records:
            values = self._reassign_values(record, field)
            if values is None:
                unchanged += 1
                continue
            # the note quotes the previous owner, so build it before writing
            body = self._note_body(record, field) if self.log_note else False
            try:
                # one savepoint per record: a single failure never aborts the batch
                with self.env.cr.savepoint():
                    record.write(values)
            except AccessError:
                # the user may not write this record: report it, never bypass the rule
                skipped += 1
            except psycopg2.OperationalError:
                # serialization failure / deadlock: let Odoo retry the whole request
                raise
            except Exception as err:  # noqa: BLE001 - one bad record must not stop the rest
                _logger.warning('Reassigning %s(%s) failed: %s', model_name, record.id, err)
                first_error = first_error or str(err)
                failed += 1
            else:
                reassigned += 1
                if body and hasattr(record, 'message_post'):
                    self._log_note(record, body)

        self.write({
            'reassigned_count': reassigned,
            'unchanged_count': unchanged,
            'skipped_count': skipped,
            'failed_count': failed,
            'remaining_count': remaining,
        })
        return self._notification(reassigned, unchanged, skipped, failed,
                                  first_error, remaining)

    def _notification(self, reassigned, unchanged, skipped, failed,
                      first_error='', remaining=0):
        self.ensure_one()
        # str(): the notification payload is JSON-serialized, and from 18.0 _() is lazy
        message = str(_(
            '%(count)s record(s) reassigned to %(user)s.',
            count=reassigned, user=self.new_user_id.display_name))
        details = []
        if unchanged:
            details.append(str(_('%s already assigned', unchanged)))
        if skipped:
            details.append(str(_('%s skipped (no write access)', skipped)))
        if failed:
            details.append(str(_('%s failed', failed)))
        if details:
            message = '%s %s' % (message, str(_('Unchanged: %s.', ', '.join(details))))
        if first_error:
            message = '%s %s' % (message, str(_('First error: %s', first_error)))
        if remaining:
            message = '%s %s' % (message, str(_(
                'Only the first %(max)s matching records were processed in '
                'this run; %(remaining)s record(s) are left. Run the action '
                'again to continue.',
                max=MAX_RECORDS, remaining=remaining)))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning' if (skipped or failed or remaining) else 'success',
                'title': str(_('Records reassigned')),
                'message': message,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
