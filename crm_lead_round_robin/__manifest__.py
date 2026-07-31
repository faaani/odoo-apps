# -*- coding: utf-8 -*-
# Part of crm_lead_round_robin. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Round-Robin Lead Assignment',
    'version': '16.0.1.0.0',
    'summary': 'Fair automatic lead distribution - every new CRM lead without a salesperson is assigned to the team members in strict rotation.',
    'description': """
Automatic lead distribution is an Enterprise-only feature in standard Odoo.
This module adds a simple, fair alternative for Community: enable a
"Round Robin" checkbox on any sales team and every new lead or opportunity
created on that team without a salesperson is assigned to the team members
in strict rotation - first member, second member, ..., then back to the
first. An hourly catch-up cron sweeps leads that arrived unassigned through
other channels (email gateway, imports, website forms).

Leads that already have a salesperson are never touched.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Sales/CRM',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['crm'],
    'data': [
        'views/crm_team_views.xml',
        'data/ir_cron_data.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
