# -*- coding: utf-8 -*-
# Part of mass_schedule_activity. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Schedule Activities in Bulk',
    'version': '14.0.1.0.1',
    'summary': 'Select many records and schedule the same activity on all of them in one step.',
    'description': """
Odoo schedules activities one record at a time. Assigning a follow-up call to
forty customers, or a review task on every overdue invoice, means opening
forty records.

This module adds "Schedule Activity" to the Action menu of every model with
activities: select the records, fill the activity once, and it is created on
all of them - with a summary of what was scheduled.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/mass_activity_wizard_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
