# -*- coding: utf-8 -*-
# Part of auto_archive_rules. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# --- Safety rails -----------------------------------------------------------
# Archiving hides records from every list, dropdown and report. All of the
# constants below exist so that a mistake in the UI cannot become a mass
# disappearance of data.

#: Hard floor enforced in code (not only in the UI): whatever a rule stores,
#: nothing younger than this many days is ever archived. A mistyped 0 can
#: therefore never empty a list.
MIN_INACTIVITY_DAYS = 7

#: Maximum number of records one rule archives in a single run. Keeps the
#: nightly transaction short and makes a runaway rule visible before it has
#: worked through a whole table.
BATCH_LIMIT = 5000

#: Models that may never be archived by a rule, whatever the user selects.
#: Archived users/companies lock people out of Odoo; the rule model itself is
#: excluded so a rule can never disable the rules.
FORBIDDEN_MODELS = ('res.users', 'res.company', 'auto.archive.rule')

#: Technical models are Odoo's own plumbing (views, actions, crons, models...).
FORBIDDEN_PREFIXES = ('ir.',)


class AutoArchiveRule(models.Model):
    _name = 'auto.archive.rule'
    _description = 'Automatic Archiving Rule'
    _order = 'sequence, id'

    name = fields.Char(
        string='Rule Name',
        required=True,
        help='Free label, e.g. "Leads untouched for a year".',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(
        default=True,
        help='Uncheck to hide this rule without deleting it. Archived rules '
             'are never applied.',
    )
    enabled = fields.Boolean(
        string='Enabled',
        default=False,
        copy=False,
        help='Rules are created disabled on purpose. The scheduled action only '
             'applies rules that are explicitly enabled here.',
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain="[('transient', '=', False)]",
        help='The model whose records this rule archives. It must have an '
             'Active field; users, companies and technical models are refused.',
    )
    model_name = fields.Char(
        related='model_id.model',
        string='Model Name',
        store=True,
        readonly=True,
    )
    filter_domain = fields.Char(
        string='Additional Filter',
        default='[]',
        help='Optional extra condition, combined with AND. Leave empty to '
             'match every record of the model that is old enough.',
    )
    inactivity_days = fields.Integer(
        string='Archive After (days)',
        default=90,
        required=True,
        help='Archive records that have not been modified for at least this '
             'many days. Values below the built-in minimum are raised to it.',
    )
    last_run = fields.Datetime(
        string='Last Run',
        readonly=True,
        copy=False,
    )
    last_run_count = fields.Integer(
        string='Archived on Last Run',
        readonly=True,
        copy=False,
    )
    archived_count = fields.Integer(
        string='Total Archived',
        default=0,
        readonly=True,
        copy=False,
        help='How many records this rule has archived since it was created.',
    )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @api.model
    def _validate_target_model(self, model_name):
        """Return the target model, or raise ValidationError saying why not.

        Called both when a rule is saved and again just before it runs: a model
        that was fine at save time can disappear when a module is uninstalled.
        """
        if not model_name:
            raise ValidationError(_('Select the model whose records should be archived.'))
        if model_name in FORBIDDEN_MODELS or model_name.startswith(FORBIDDEN_PREFIXES):
            raise ValidationError(_(
                'Automatic archiving is not allowed on "%s". Users, companies '
                'and technical (ir.*) models are protected, because archiving '
                'them would lock people out of Odoo or break the database.'
            ) % model_name)
        model = self.env.get(model_name)
        if model is None:
            raise ValidationError(_(
                'The model "%s" does not exist (its module may have been '
                'uninstalled).'
            ) % model_name)
        if model._abstract or model._transient or not model._auto:
            raise ValidationError(_(
                'The model "%s" has no regular database table, its records '
                'cannot be archived.'
            ) % model_name)
        if 'active' not in model._fields:
            raise ValidationError(_(
                'The model "%s" has no "Active" field, so its records cannot '
                'be archived. Pick a model that supports archiving.'
            ) % model_name)
        if not model._fields['active'].store:
            # A computed/related "active" with no column can neither be
            # searched nor written: the rule would silently do nothing.
            raise ValidationError(_(
                'The "Active" field of model "%s" is computed on the fly, so '
                'it cannot be searched or written. Pick a model that stores it.'
            ) % model_name)
        if 'write_date' not in model._fields:
            raise ValidationError(_(
                'The model "%s" does not track a last modification date, so '
                '"not modified for N days" cannot be evaluated on it.'
            ) % model_name)
        return model

    @api.constrains('model_id')
    def _check_model_id(self):
        for rule in self:
            rule._validate_target_model(rule.model_id.model)

    @api.constrains('inactivity_days')
    def _check_inactivity_days(self):
        for rule in self:
            if rule.inactivity_days < MIN_INACTIVITY_DAYS:
                raise ValidationError(_(
                    'A rule must wait at least %(min)s days before archiving. '
                    'Rule "%(rule)s" is set to %(days)s.'
                ) % {
                    'min': MIN_INACTIVITY_DAYS,
                    'rule': rule.name or '',
                    'days': rule.inactivity_days,
                })

    @api.constrains('filter_domain', 'model_id')
    def _check_filter_domain(self):
        for rule in self:
            domain = rule._parse_filter_domain()
            if not domain or not rule.model_id.model:
                continue
            # A filter that names a field the model does not have would only
            # blow up at night, inside the cron, where nobody sees it. Try it
            # once here so the mistake is refused while the user is looking.
            model = rule._validate_target_model(rule.model_id.model)
            try:
                model.sudo().search(domain, limit=1)
            except Exception as error:  # noqa: BLE001 - any failure = unusable filter
                raise ValidationError(_(
                    'The additional filter of rule "%(rule)s" cannot be '
                    'applied to %(model)s: %(error)s'
                ) % {'rule': rule.name or '', 'model': rule.model_id.model,
                     'error': error})

    # ------------------------------------------------------------------
    # Selection of the records to archive
    # ------------------------------------------------------------------
    def _parse_filter_domain(self):
        """The extra filter, as a domain list. Raises ValidationError if the
        text the user typed is not a usable domain."""
        self.ensure_one()
        raw = (self.filter_domain or '').strip() or '[]'
        try:
            domain = safe_eval(raw)
        except Exception as error:  # noqa: BLE001 - any eval problem is a bad domain
            raise ValidationError(_(
                'The additional filter of rule "%(rule)s" is not a valid '
                'domain: %(error)s'
            ) % {'rule': self.name or '', 'error': error})
        if (isinstance(domain, tuple) and len(domain) == 3
                and isinstance(domain[0], str)):
            # A single condition typed without its enclosing brackets. Spliced
            # in as-is it would become three separate domain elements.
            domain = [domain]
        if not isinstance(domain, (list, tuple)):
            raise ValidationError(_(
                'The additional filter of rule "%s" must be a domain list, '
                'for example [("stage_id.is_won", "=", False)].'
            ) % (self.name or ''))
        return list(domain)

    def _effective_inactivity_days(self):
        """The age actually used, never below the hard floor. This is the guard
        that survives a mistyped 0 written straight into the database."""
        self.ensure_one()
        return max(self.inactivity_days or 0, MIN_INACTIVITY_DAYS)

    def _protected_record_ids(self):
        """Records that survive even when their model is an allowed target.

        FORBIDDEN_MODELS stops res.users and res.company being named directly,
        but every user and every company also owns a res.partner row — and
        res.partner is a legitimate, advertised target ("stale contacts").
        Odoo core only refuses to archive the partner of an *active* user and
        never looks at companies at all, so without this the blocklist would
        be defeated by the module's own headline use case. active_test=False
        on both searches is what covers the archived-user case.
        """
        self.ensure_one()
        if self.model_name != 'res.partner':
            return []
        users = self.env['res.users'].sudo().with_context(
            active_test=False).search([])
        companies = self.env['res.company'].sudo().with_context(
            active_test=False).search([])
        return (users.partner_id | companies.partner_id).ids

    def _target_domain(self):
        self.ensure_one()
        cutoff = fields.Datetime.now() - timedelta(days=self._effective_inactivity_days())
        # Two normalised domains concatenated is a plain AND, so an extra
        # filter starting with a prefix operator stays correctly grouped.
        domain = [
            ('active', '=', True),
            ('write_date', '<', fields.Datetime.to_string(cutoff)),
        ] + self._parse_filter_domain()
        protected = self._protected_record_ids()
        if protected:
            domain.append(('id', 'not in', protected))
        return domain

    def _target_records(self):
        """The records this rule would archive right now.

        Used by both the preview and the run, so what the preview shows is
        exactly what the next run acts on. Oldest first, so the batch cap
        below always bites on the freshest records, never the stalest.
        """
        self.ensure_one()
        model = self._validate_target_model(self.model_name)
        return model.sudo().with_context(active_test=False).search(
            self._target_domain(), limit=BATCH_LIMIT, order='write_date, id')

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------
    def _run_rule(self):
        """Archive this rule's records. Returns how many were archived."""
        self.ensure_one()
        records = self._target_records()
        archived = 0
        skipped = 0
        if records:
            try:
                # Happy path: one statement for the whole batch, still inside a
                # savepoint so a failure cannot poison the rest of the run.
                with self.env.cr.savepoint():
                    records.write({'active': False})
                archived = len(records)
            except Exception:  # noqa: BLE001 - fall back to isolate the bad ones
                _logger.info(
                    'auto_archive_rules: rule %r could not archive its batch '
                    'in one go, retrying one record at a time.', self.name)
                for record in records:
                    try:
                        # One savepoint per record: a record blocked by a
                        # constraint, an override or an access rule is logged
                        # and skipped, it never aborts the rest of the run.
                        with self.env.cr.savepoint():
                            record.write({'active': False})
                    except Exception as error:  # noqa: BLE001 - skip, don't stop
                        skipped += 1
                        # A record refused by a constraint is a routine outcome
                        # here, not a fault: warn, and keep the traceback for
                        # debug so nightly runs cannot flood the error log.
                        _logger.warning(
                            'auto_archive_rules: rule %r skipped %s(%s): %s',
                            self.name, self.model_name, record.id, error)
                        _logger.debug('auto_archive_rules: skipped record detail',
                                      exc_info=True)
                    else:
                        archived += 1
        if skipped:
            _logger.warning('auto_archive_rules: rule %r skipped %s record(s).',
                            self.name, skipped)
        if records and not archived and len(records) == BATCH_LIMIT:
            # Every record of a full batch refused: the rule can never reach
            # the ones behind them, so it would stall silently for ever.
            _logger.warning(
                'auto_archive_rules: rule %r matched a full batch of %s %s '
                'record(s) and archived none of them; it is stuck.',
                self.name, BATCH_LIMIT, self.model_name)
        self.sudo().write({
            'last_run': fields.Datetime.now(),
            'last_run_count': archived,
            'archived_count': self.archived_count + archived,
        })
        _logger.info('auto_archive_rules: rule %r archived %s %s record(s).',
                     self.name, archived, self.model_name)
        return archived

    @api.model
    def _cron_archive(self):
        """Daily entry point: apply every enabled rule."""
        rules = self.search([('enabled', '=', True)])
        total = 0
        for rule in rules:
            try:
                # One savepoint per rule too: a broken rule (deleted model,
                # unusable filter) must not cancel the work of the others.
                with self.env.cr.savepoint():
                    total += rule._run_rule()
            except Exception:  # noqa: BLE001 - keep going with the next rule
                _logger.exception(
                    'auto_archive_rules: rule %r failed and was skipped.',
                    rule.name)
        _logger.info('auto_archive_rules: %s rule(s) archived %s record(s).',
                     len(rules), total)
        return total

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def action_preview(self):
        """Dry run: open the records that would be archived, change nothing."""
        self.ensure_one()
        records = self._target_records()
        if not records:
            return self._notify(_(
                'Nothing to archive: no %s record is older than %s days and '
                'matches the filter.'
            ) % (self.model_id.name, self._effective_inactivity_days()))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Preview: %s') % self.name,
            'res_model': self.model_name,
            'view_mode': 'tree,form',
            'domain': [('id', 'in', records.ids)],
            'context': {'create': False},
            'target': 'current',
        }

    def action_run_now(self):
        """Apply this rule immediately, without waiting for the daily job."""
        self.ensure_one()
        archived = self._run_rule()
        return self._notify(_('%(count)s %(model)s record(s) archived.') % {
            'count': archived,
            'model': self.model_id.name,
        }, level='success' if archived else 'warning')

    def _notify(self, message, level='info'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Automatic Archiving'),
                'message': message,
                'type': level,
                'sticky': False,
            },
        }
