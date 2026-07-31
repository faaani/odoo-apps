# -*- coding: utf-8 -*-
# Part of crm_lead_round_robin. License: LGPL-3.
from odoo import fields, models


class CrmTeam(models.Model):
    _inherit = 'crm.team'

    assignment_round_robin = fields.Boolean(
        string='Round Robin Assignment',
        default=False,
        help='When enabled, every new lead or opportunity created on this '
             'team without a salesperson is assigned to the team members in '
             'strict rotation. Leads that already have a salesperson are '
             'never touched.')
    rr_last_member_id = fields.Many2one(
        'res.users', string='Last Round-Robin Assignee',
        readonly=True, copy=False,
        help='The member who received the last round-robin assignment. '
             'The next lead goes to the following member in the rotation.')

    def _rr_candidates(self, company=None):
        """Active team members eligible for a lead of the given company.

        crm.lead.user_id is check_company=True from 15.0 on: picking a member
        who is not allowed in the lead's company would make the whole lead
        creation fail with a ValidationError, so such members are skipped.
        """
        self.ensure_one()
        members = self.member_ids.filtered('active')
        if company:
            members = members.filtered(lambda user: company in user.company_ids)
        return members.sorted('id')

    def _rr_plan_assignees(self, count, company=None):
        """Return a list of ``count`` user ids in strict rotation and advance
        the stored pointer exactly once.

        Rotation order is the eligible members sorted by id; the first pick is
        the member after ``rr_last_member_id``, wrapping around. Returns an
        empty list when the team has no eligible member.

        The pointer is written with sudo(): salespeople may create leads
        without having write access on crm.team, and only this internal
        technical field is touched (never an access decision).
        """
        self.ensure_one()
        members = self._rr_candidates(company=company)
        if not members or count <= 0:
            return []
        member_ids = members.ids
        last_id = self.rr_last_member_id.id
        start = (member_ids.index(last_id) + 1) if last_id in member_ids else 0
        plan = [member_ids[(start + n) % len(member_ids)] for n in range(count)]
        self.sudo().write({'rr_last_member_id': plan[-1]})
        return plan
