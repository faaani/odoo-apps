# -*- coding: utf-8 -*-
# Part of archive_reason_log. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Archive with a Reason',
    'version': '16.0.1.0.0',
    'summary': 'Archive records from the Action menu with a reason, keep it on the record and in a searchable log.',
    'description': """
Archiving hides a record from everyone with one click, and nobody ever records
why. Six months later the question "why is this customer archived?" has no
answer anywhere in the database.

This module adds "Archive with Reason" to the Action menu of every model that
can be archived and has a chatter:

* pick the records, choose a reason from a list you configure,
* type a free-text explanation when the reason asks for one,
* the records are archived, the reason is stored on each of them and a single
  note is posted in each record's chatter,
* everything lands in an "Archive Log" report: what was archived, by whom, when
  and why - filterable by reason, model, user and date.

Safety is built in. Users, companies and technical (ir.*) records are never
archived. Contacts that belong to a user or to a company are excluded from a
contact selection, so a company can never lose its own contact. Every record is
archived in its own savepoint: one failure never aborts the batch.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/archive_reason_log_rules.xml',
        'data/archive_reason_data.xml',
        'wizard/archive_reason_wizard_views.xml',
        'views/archive_reason_views.xml',
        'views/archive_reason_log_views.xml',
        'views/archive_reason_menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
