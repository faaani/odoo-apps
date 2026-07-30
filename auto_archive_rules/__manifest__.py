# -*- coding: utf-8 -*-
# Part of auto_archive_rules. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Automatic Archiving Rules',
    'version': '19.0.1.0.0',
    'summary': 'Archive stale records automatically: pick a model, a filter and an age, a daily job does the rest.',
    'description': """
Lost leads from 2019, tasks closed two years ago, contacts nobody has touched
since the import — Odoo keeps every one of them in every list, every dropdown
and every report, forever. Odoo has no built-in way to archive them on a
schedule, so lists only ever grow.

This module adds Automatic Archiving Rules: choose a model, add an optional
extra filter, and set "archive records not modified for N days". A daily
scheduled action applies every enabled rule and keeps a running count of what
it archived.

Because archiving hides records, the module is deliberately cautious:

* every rule is DISABLED when created — nothing happens until you turn it on;
* a hard minimum age is enforced in code, so a mistyped 0 can never wipe a list;
* users, companies and technical (ir.*) models are refused outright;
* models without an Active field are refused when the rule is saved;
* a Preview button shows exactly which records would be archived, changing
  nothing;
* one failing record is logged and skipped, it never aborts the run.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/auto_archive_rule_views.xml',
        'data/ir_cron_data.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
