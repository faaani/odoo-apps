# -*- coding: utf-8 -*-
# Part of activity_overdue_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Overdue Activities Report',
    'version': '16.0.1.0.0',
    'summary': 'Cross-model report of open activities: who is late, on which document, and by how many days.',
    'description': """
Odoo shows each user their own late activities in the systray, and each document
its own activity list. There is no single place where a manager can see what the
whole team is late on.

This module adds a read-only report over mail.activity with one row per open
activity:

* the person the activity is assigned to and the activity type,
* the document it belongs to - model, live name, and a button that opens it,
* the due date and the number of days the activity is overdue.

Filters for Overdue, Due Today, Due This Week, Overdue 7+/30+ days, assigned to
me and scheduled by me. Group by assignee, activity type, document model, status
or due date, and switch to the pivot or graph view to chart workload (Activities
count and average days overdue are both measures).

Visibility: a row is shown when the activity is assigned to you, or when you are
allowed to read the document it is attached to - the report re-checks the record
rules of each underlying document, one query per model. It never runs as
superuser and never widens what you can already see.

The report is a database view over open activities only. Activities that were
marked done or cancelled never appear. Nothing is written: no activity and no
document is modified.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/activity_overdue_report_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
