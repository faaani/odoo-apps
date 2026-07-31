# -*- coding: utf-8 -*-
# Part of activity_summary_digest. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Daily Activity Digest Email',
    'version': '15.0.1.0.0',
    'summary': 'One morning email per user listing the activities they must deal with today, grouped by document type, with a link to each record.',
    'description': """
Odoo activities only nag you inside Odoo. Close the tab and the reminder is
gone: calls, follow-ups and to-dos quietly go past their due date because
nothing reaches people where they actually look — their inbox.

This module sends every user who opted in one digest email each morning with:

* the activities assigned to them that are due today or already overdue,
* grouped by document type (Contact, Sales Order, Project Task, ...),
* each line showing the activity type, its summary and its due date, with
  overdue lines clearly marked,
* a direct link that opens the document in Odoo.

Nothing is sent to a user who has no activity due — you never get an empty
"you have 0 activities" email. Each digest is built in the recipient's own
language and their own timezone, so "due today" means today where they are,
not where the server is.

Only activities assigned to the recipient are listed, and only on documents
that recipient is still allowed to read. Activities pointing at a record that
was deleted in the meantime are skipped instead of breaking the digest, and a
failure for one user never stops the run for the others.

The digest is read-only: it never modifies, reschedules or closes an activity.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail', 'base_setup'],
    'data': [
        'views/res_users_views.xml',
        'views/res_config_settings_views.xml',
        'data/ir_cron_data.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
