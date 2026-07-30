# -*- coding: utf-8 -*-
# Part of archive_reason_log. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..models.mail_thread import SKIP_AUDIT_CTX

_logger = logging.getLogger(__name__)

#: Models this tool refuses outright, whatever the user selects. Archiving a
#: user or a company breaks logins and company data; ir.* rows are the ORM's own
#: plumbing (views, fields, rules) and are never business records.
FORBIDDEN_MODELS = ('res.users', 'res.company')
FORBIDDEN_PREFIXES = ('ir.',)

#: Hard cap on one run. Each record costs a savepoint, a write, a log row and a
#: chatter message, so an unbounded "select all" would run the worker out of
#: time and roll the whole batch back. Refusing loudly beats a silent timeout.
MAX_RECORDS = 500


class ArchiveReasonWizard(models.TransientModel):
    _name = 'archive.reason.wizard'
    _description = 'Archive with Reason'

    res_model = fields.Char(string='Model', readonly=True)
    model_label = fields.Char(string='Model Label', readonly=True)
    record_count = fields.Integer(string='Records to archive', readonly=True)
    excluded_count = fields.Integer(string='Skipped records', readonly=True)
    reason_id = fields.Many2one(
        'archive.reason', string='Reason', required=True,
        domain="['|', ('model_ids', '=', False), ('model_ids.model', '=', res_model)]")
    note_mode = fields.Selection(
        related='reason_id.note_mode', string='Explanation Policy', readonly=True)
    reason_description = fields.Char(related='reason_id.description', readonly=True)
    note = fields.Text(string='Explanation')

    # ------------------------------------------------------------------
    # eligibility
    # ------------------------------------------------------------------
    @api.model
    def _archive_model_error(self, model_name):
        """Return a user-readable refusal for ``model_name``, or None if it is fine."""
        if not model_name or model_name not in self.env:
            return _('No records were selected, so there is nothing to archive.')
        if model_name in FORBIDDEN_MODELS or model_name.startswith(FORBIDDEN_PREFIXES):
            return _(
                'Records of "%s" are never archived by this tool: archiving a user, '
                'a company or a technical record would break the database.'
            ) % model_name
        Model = self.env[model_name]
        if Model._abstract or Model._transient or not Model._auto:
            return _('"%s" does not store real records, so nothing can be archived.') % model_name
        label = Model._description or model_name
        if 'active' not in Model._fields:
            return _(
                '"%s" has no Archived flag, so its records cannot be archived at all.'
            ) % label
        if 'message_ids' not in Model._fields or not hasattr(Model, 'message_post'):
            return _(
                '"%s" has no chatter, so the reason could not be kept with the record.'
            ) % label
        return None

    @api.model
    def _protected_records(self, records):
        """Records that must never be archived even when the model is allowed."""
        protected = records.browse()
        if records._name == 'res.partner':
            # A user's contact and a company's own contact must stay active:
            # archiving them breaks the login or the company itself.
            # sudo() here only widens a *protective* lookup - it can exclude more
            # records, never grant the user anything.
            partner_ids = records.ids
            users = self.env['res.users'].sudo().with_context(
                active_test=False).search([('partner_id', 'in', partner_ids)])
            companies = self.env['res.company'].sudo().with_context(
                active_test=False).search([('partner_id', 'in', partner_ids)])
            keep = set(users.mapped('partner_id').ids) | set(companies.mapped('partner_id').ids)
            if keep:
                protected = records.filtered(lambda record: record.id in keep)
        return protected

    @api.model
    def _split_selection(self, records):
        """Return (to_archive, protected, already_archived)."""
        protected = self._protected_records(records)
        remaining = records - protected
        already = remaining.filtered(lambda record: not record.active)
        return remaining - already, protected, already

    # ------------------------------------------------------------------
    # wizard
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super(ArchiveReasonWizard, self).default_get(fields_list)
        context = self.env.context
        model_name = context.get('active_model')
        ids = list(context.get('active_ids') or [])
        if not ids and context.get('active_id'):
            ids = [context['active_id']]
        error = self._archive_model_error(model_name)
        if error:
            raise UserError(error)
        records = self.env[model_name].with_context(
            active_test=False).browse(ids).exists()
        to_archive, protected, already = self._split_selection(records)
        res.update({
            'res_model': model_name,
            'model_label': self.env[model_name]._description or model_name,
            'record_count': len(to_archive),
            'excluded_count': len(protected) + len(already),
        })
        return res

    @api.model
    def _archive_message_body(self, reason, note):
        """Chatter note posted on each archived record (HTML-safe)."""
        body = Markup('<p><b>%s</b><br/>%s: %s</p>') % (
            _('Record archived with a reason'), _('Reason'), reason.name)
        if note:
            body += Markup('<p>%s</p>') % escape(note).replace('\n', Markup('<br/>'))
        return body

    def action_archive_records(self):
        self.ensure_one()
        context = self.env.context
        # the stored value was already validated by default_get; the context is
        # only the fallback for a wizard opened outside the Action menu
        model_name = self.res_model or context.get('active_model')
        error = self._archive_model_error(model_name)
        if error:
            raise UserError(error)
        ids = list(context.get('active_ids') or [])
        if not ids and context.get('active_id'):
            ids = [context['active_id']]
        records = self.env[model_name].with_context(
            active_test=False).browse(ids).exists()
        if not records:
            raise UserError(_('The selected records no longer exist.'))

        reason = self.reason_id
        note = (self.note or '').strip()
        if reason.note_mode == 'required' and not note:
            raise UserError(
                _('The reason "%s" requires an explanation. Describe why these '
                  'records are archived before continuing.') % reason.name)
        if reason.note_mode == 'forbidden' and note:
            raise UserError(
                _('The reason "%s" does not accept a free-text explanation. '
                  'Clear the Explanation box, or pick another reason.') % reason.name)
        if reason.model_ids and model_name not in reason.model_ids.mapped('model'):
            raise UserError(
                _('The reason "%(reason)s" cannot be used on %(model)s.')
                % {'reason': reason.name, 'model': model_name})

        to_archive, protected, already = self._split_selection(records)
        if not to_archive:
            raise UserError(
                _('None of the selected records can be archived: %(protected)s are '
                  'protected and %(already)s are archived already.')
                % {'protected': len(protected), 'already': len(already)})
        if len(to_archive) > MAX_RECORDS:
            raise UserError(
                _('This tool archives at most %(max)s records at a time, and '
                  '%(count)s were selected. Narrow the selection and try again - '
                  'nothing has been archived.')
                % {'max': MAX_RECORDS, 'count': len(to_archive)})

        model_id = self.env['ir.model']._get(model_name).id
        # sudo(): the log is an audit table, so ordinary users hold no create
        # right on it (see ir.model.access.csv) and cannot forge entries through
        # RPC. The author is still recorded from the real uid below.
        Log = self.env['archive.reason.log'].sudo()
        archived = 0
        not_noted = 0
        failed = []
        for record in to_archive:
            try:
                # one savepoint per record: a record that refuses to archive
                # (record rule, python constraint, ...) never aborts the batch
                with self.env.cr.savepoint():
                    record_name = record.display_name or (
                        '%s,%s' % (model_name, record.id))
                    record.with_context(**{SKIP_AUDIT_CTX: True}).write({
                        'active': False,
                        'archive_reason': reason.name,
                        'archive_reason_note': note or False,
                    })
                    Log.create({
                        'model_id': model_id,
                        'res_model': model_name,
                        'res_id': record.id,
                        'record_name': record_name,
                        'reason_id': reason.id,
                        'note': note or False,
                        'user_id': self.env.uid,
                        'archive_date': fields.Datetime.now(),
                    })
                archived += 1
            except (UserError, AccessError) as err:
                # the common case is a user without write access on the model,
                # so it must be in the log AND in the message shown back
                _logger.warning(
                    'archive_reason_log: could not archive %s,%s: %s',
                    model_name, record.id, err)
                failed.append((record.id, str(err)))
                continue
            except Exception as err:  # noqa: BLE001 - one bad record must not stop the batch
                _logger.exception(
                    'archive_reason_log: could not archive %s,%s.',
                    model_name, record.id)
                failed.append((record.id, str(err)))
                continue
            # The chatter note is posted separately, in its own savepoint: a user
            # whose account carries no email address cannot post in Odoo at all,
            # and that must not cost them the archive. The reason is on the
            # record and in the log either way, and the count is reported below.
            try:
                with self.env.cr.savepoint():
                    record.message_post(
                        body=self._archive_message_body(reason, note))
            except Exception as err:  # noqa: BLE001 - the note is best effort
                _logger.warning(
                    'archive_reason_log: archived %s,%s but could not post the '
                    'chatter note: %s', model_name, record.id, err)
                not_noted += 1

        return self._notification(
            archived, protected, already, failed, reason, not_noted)

    def _notification(self, archived, protected, already, failed, reason,
                      not_noted=0):
        parts = [_('%(count)s record(s) archived with the reason "%(reason)s".')
                 % {'count': archived, 'reason': reason.name}]
        if already:
            parts.append(_('%s were already archived.') % len(already))
        if protected:
            parts.append(
                _('%s protected record(s) were skipped (a user\'s or a company\'s '
                  'contact is never archived).') % len(protected))
        if not_noted:
            parts.append(
                _('%s were archived but no chatter note could be posted on them '
                  '(see the server log).') % not_noted)
        if failed:
            parts.append(
                _('%(count)s could not be archived. First error: %(error)s')
                % {'count': len(failed), 'error': failed[0][1]})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning' if (failed or not_noted) else 'success',
                'title': _('Archived with a reason'),
                'message': ' '.join(parts),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    # ------------------------------------------------------------------
    # Action-menu bindings
    # ------------------------------------------------------------------
    @api.model
    def _archivable_model_names(self):
        return [name for name in sorted(self.env.registry)
                if self._archive_model_error(name) is None]

    @api.model
    def _sync_action_bindings(self):
        """Add "Archive with Reason" to the Action menu of every archivable model.

        Called once at install and on demand from the Settings menu; existing
        entries are left alone, so an administrator who removed one keeps it
        removed until the next explicit refresh.
        """
        if not (self.env.su or self.env.user.has_group('base.group_system')):
            raise AccessError(
                _('Only a Settings administrator can refresh the Action menus.'))
        template = self.env.ref(
            'archive_reason_log.action_archive_reason_wizard',
            raise_if_not_found=False)
        if not template:
            return False
        # sudo(): creating an ir.actions.act_window is a system-level write and
        # the caller has just been checked to be a Settings administrator.
        Action = self.env['ir.actions.act_window'].sudo()
        IrModelData = self.env['ir.model.data'].sudo()
        names = self._archivable_model_names()
        models_by_name = {
            model.model: model
            for model in self.env['ir.model'].sudo().search([('model', 'in', names)])
        }
        # a model already reachable from the Action menu is left untouched, so
        # this stays idempotent next to the binding shipped in the data files
        already_bound = set(Action.search([
            ('res_model', '=', 'archive.reason.wizard'),
            ('binding_model_id', '!=', False),
        ]).mapped('binding_model_id.model'))
        group = self.env.ref('base.group_user', raise_if_not_found=False)
        created = 0
        for name in names:
            ir_model = models_by_name.get(name)
            if not ir_model or name in already_bound:
                continue
            xmlid = 'binding_%s' % name.replace('.', '_')
            if IrModelData.search_count([('module', '=', 'archive_reason_log'),
                                         ('name', '=', xmlid)]):
                continue
            action = Action.create({
                'name': template.name,
                'res_model': 'archive.reason.wizard',
                'view_mode': 'form',
                'target': 'new',
                'binding_model_id': ir_model.id,
                'binding_view_types': 'list,form',
                'groups_id': [(6, 0, group.ids)] if group else False,
            })
            IrModelData.create({
                'module': 'archive_reason_log',
                'name': xmlid,
                'model': 'ir.actions.act_window',
                'res_id': action.id,
                # noupdate: a module upgrade must not sweep these generated rows
                'noupdate': True,
            })
            created += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Action menus updated'),
                'message': _('%(created)s model(s) added, %(total)s model(s) can now '
                             'be archived with a reason.')
                % {'created': created, 'total': len(names)},
            },
        }
