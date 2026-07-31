# -*- coding: utf-8 -*-
# Part of crm_lead_round_robin. License: LGPL-3.
import logging

from psycopg2 import InterfaceError, OperationalError

from odoo import api, models

_logger = logging.getLogger(__name__)

# Cap the hourly catch-up so a single run can never churn a huge backlog.
RR_CRON_BATCH = 500


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    @api.model_create_multi
    def create(self, vals_list):
        # This hook runs BEFORE super() on purpose: crm.lead.user_id has
        # default=lambda self: self.env.user, so after creation it is
        # impossible to tell "the caller sent no salesperson" apart from
        # "the caller explicitly picked the current user". Do not move this
        # to a post-create pass.
        team_model = self.env['crm.team']
        company_model = self.env['res.company']
        new_vals_list = []
        for vals in vals_list:
            # an explicit team_id in vals always wins over the context default,
            # including an explicit team_id=False (same rule as the core ORM)
            if 'team_id' in vals:
                team_id = vals['team_id']
            else:
                team_id = self.env.context.get('default_team_id')
            if (not vals.get('user_id') and isinstance(team_id, int)
                    and not isinstance(team_id, bool)):
                # sudo: whether the team rotates is a system-level decision;
                # the creating user may not be allowed to read the team
                # (multi-company rules) and must not get an AccessError from
                # this module. Nothing is written on the user's behalf here.
                team = team_model.browse(team_id).exists().sudo()
                if team and team.assignment_round_robin:
                    company = (company_model.browse(vals['company_id'])
                               if vals.get('company_id') else team.company_id)
                    plan = team._rr_plan_assignees(1, company=company)
                    if plan:
                        # copy: never mutate caller-owned vals dicts (the same
                        # dict object may be reused for several creates).
                        # team_id is NOT injected: when it came from vals it is
                        # already there, and a context default must stay a
                        # default for the ORM to apply.
                        vals = dict(vals, user_id=plan[0])
            new_vals_list.append(vals)
        return super().create(new_vals_list)

    @api.model
    def _cron_rr_assign_leads(self):
        """Hourly catch-up: assign unassigned, active (non-lost) leads of
        round-robin teams.

        The overall budget (RR_CRON_BATCH) is split evenly over the teams so
        one team's backlog can never starve the others. Each team is handled
        in its own savepoint with a single pointer write and one batched
        user_id write per assignee, keeping the crm_team row lock window
        short. One failing team never aborts the run.
        """
        team_model = self.env['crm.team']
        teams = team_model.search([('assignment_round_robin', '=', True)])
        # Community 15.0+ ships its own (opt-in) rule-based assignment that
        # also claims userless leads. Where an admin enabled it on a team,
        # let core win the catch-up instead of competing with it.
        if 'assignment_auto_enabled' in team_model._fields:
            teams = teams.filtered(lambda t: not t.assignment_auto_enabled)
        if not teams:
            return
        per_team = max(1, RR_CRON_BATCH // len(teams))
        for team in teams:
            try:
                with self.env.cr.savepoint():
                    leads = self.search([
                        ('user_id', '=', False),
                        ('team_id', '=', team.id),
                    ], order='id', limit=per_team)
                    if not leads:
                        continue
                    # rotate per lead company: eligibility can differ
                    buckets = {}
                    for lead in leads:
                        buckets.setdefault(lead.company_id, self.browse())
                        buckets[lead.company_id] |= lead
                    for company, bucket in buckets.items():
                        plan = team._rr_plan_assignees(
                            len(bucket), company=company or team.company_id)
                        if not plan:
                            continue
                        by_user = {}
                        for lead, user_id in zip(bucket, plan):
                            by_user.setdefault(user_id, []).append(lead.id)
                        for user_id, lead_ids in by_user.items():
                            self.browse(lead_ids).write({'user_id': user_id})
            except (OperationalError, InterfaceError):
                # connection loss / serialization failure: retryable at the
                # cron level, never swallow
                raise
            except Exception:
                _logger.exception(
                    'crm_lead_round_robin: could not assign leads of team %s',
                    team.id)
