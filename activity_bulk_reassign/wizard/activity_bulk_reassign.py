# -*- coding: utf-8 -*-
# Part of activity_bulk_reassign. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class ActivityBulkReassign(models.TransientModel):
    _name = 'activity.bulk.reassign'
    _description = 'Reassign Activities in Bulk'

    from_user_id = fields.Many2one(
        'res.users', string='From User', required=True,
        domain="[('share', '=', False)]",
        # someone who left the company is usually archived: they must stay
        # selectable, otherwise the main use case is out of reach
        context={'active_test': False},
        help='The user whose open activities have to be handed over.')
    to_user_id = fields.Many2one(
        'res.users', string='To User', required=True,
        domain="[('share', '=', False)]",
        default=lambda self: self.env.user,
        help='The user who will take the activities over.')
    activity_type_ids = fields.Many2many(
        'mail.activity.type', string='Activity Types',
        help='Restrict the move to these activity types. Leave empty to move every type.')
    date_from = fields.Date(
        string='Due From', help='Only activities due on or after this date. Leave empty for no lower bound.')
    date_to = fields.Date(
        string='Due To', help='Only activities due on or before this date. Leave empty for no upper bound.')
    log_note = fields.Boolean(
        string='Log a Note', default=True,
        help='Log a note in the chatter of every document whose activity was reassigned.')
    activity_count = fields.Integer(
        string='Matching Activities', compute='_compute_activity_count',
        help='Open activities that match the filters and that you are allowed to reassign.')
    # not shown in the form (the wizard closes on success): kept as the
    # programmatic result of the last run
    reassigned_count = fields.Integer(string='Reassigned Activities', readonly=True)

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------
    def _activity_domain(self):
        """Domain selecting the OPEN activities of the source user."""
        self.ensure_one()
        domain = [('user_id', '=', self.from_user_id.id)]
        if 'active' in self.env['mail.activity']._fields:
            # From 17.0 on, a completed activity is kept as an archived row.
            # Older series delete it outright, so there is nothing to exclude.
            domain.append(('active', '=', True))
        if self.activity_type_ids:
            domain.append(('activity_type_id', 'in', self.activity_type_ids.ids))
        if self.date_from:
            domain.append(('date_deadline', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_deadline', '<=', self.date_to))
        return domain

    def _filter_writable(self, activities):
        """Keep only the activities the CURRENT user may write.

        Never uses sudo(): the check goes through the very same access rules
        Odoo applies when the activity is edited by hand.
        """
        if not activities:
            return activities
        if hasattr(activities, '_filtered_access'):
            # 18.0 and above: batched equivalent of filtered(has_access(...)),
            # which would otherwise cost one query per activity
            return activities._filtered_access('write')
        return activities._filter_access_rules_python('write')

    def _get_activities(self):
        """Open activities of the source user that this user is allowed to move.

        The search runs with the current user's own rights, so the previewed
        count is exactly what a reassignment would move.
        """
        self.ensure_one()
        if not self.from_user_id:
            return self.env['mail.activity']
        activities = self.env['mail.activity'].search(self._activity_domain())
        return self._filter_writable(activities)

    @api.depends('from_user_id', 'activity_type_ids', 'date_from', 'date_to')
    def _compute_activity_count(self):
        for wizard in self:
            wizard.activity_count = len(wizard._get_activities())

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_('"Due From" must come before "Due To".'))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_reassign(self):
        self.ensure_one()
        if not self.from_user_id or not self.to_user_id:
            raise UserError(_('Choose both the user to take the activities from and the user to give them to.'))
        if self.from_user_id == self.to_user_id:
            # Nothing to do: leave every activity exactly where it is.
            self.reassigned_count = 0
            return self._notification(
                _('%s already owns these activities, nothing was changed.') % self.to_user_id.display_name,
                notification_type='warning')

        matching = self.env['mail.activity'].search(self._activity_domain())
        activities = self._filter_writable(matching)
        if not activities:
            if matching:
                # tell the two cases apart: widening the filters would not help
                raise UserError(
                    _('%s open activity(ies) match these filters, but you are not allowed to reassign any of them.')
                    % len(matching))
            raise UserError(
                _('No open activity of %s matches these filters, so there is nothing to reassign.')
                % self.from_user_id.display_name)

        documents = self._collect_documents(activities)
        try:
            activities.write({'user_id': self.to_user_id.id})
        except UserError as error:
            # up to 16.0, core refuses the whole write when the new assignee
            # cannot read one of the documents
            raise UserError(
                _('%(target)s cannot take these activities over: %(reason)s')
                % {'target': self.to_user_id.display_name, 'reason': error.args[0] if error.args else ''})
        self.reassigned_count = len(activities)
        skipped = self._log_notes(documents) if self.log_note else 0
        message = _('%(count)s activity(ies) moved from %(source)s to %(target)s.') % {
            'count': self.reassigned_count,
            'source': self.from_user_id.display_name,
            'target': self.to_user_id.display_name,
        }
        if skipped:
            return self._notification(
                message + ' ' + (_('%s document(s) could not be annotated.') % skipped),
                notification_type='warning')
        return self._notification(message)

    def _collect_documents(self, activities):
        """Group the activity summaries per related document, before the move."""
        documents = {}
        for activity in activities:
            if not activity.res_model or not activity.res_id:
                continue  # activities not attached to a document have no chatter
            summary = activity.summary or activity.activity_type_id.display_name or _('Activity')
            documents.setdefault((activity.res_model, activity.res_id), []).append(summary)
        return documents

    def _log_notes(self, documents):
        """Log one note per affected document; return how many were skipped."""
        self.ensure_one()
        header = _('Activities reassigned from %(source)s to %(target)s:') % {
            'source': self.from_user_id.display_name,
            'target': self.to_user_id.display_name,
        }
        skipped = 0
        for (res_model, res_id), summaries in documents.items():
            if res_model not in self.env:
                continue
            record = self.env[res_model].browse(res_id).exists()
            if not record or not hasattr(record, 'message_post'):
                continue
            items = Markup().join(Markup('<li>%s</li>') % summary for summary in summaries)
            body = Markup('<p>%s</p><ul>%s</ul>') % (header, items)
            try:
                # A savepoint keeps one unloggable document from aborting the move.
                with self.env.cr.savepoint():
                    record.message_post(body=body, subtype_xmlid='mail.mt_note')
            except (AccessError, UserError):
                # the move itself stands; say so instead of silently dropping it
                skipped += 1
        return skipped

    def _notification(self, message, notification_type='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': notification_type,
                'title': _('Reassign Activities'),
                'message': message,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
