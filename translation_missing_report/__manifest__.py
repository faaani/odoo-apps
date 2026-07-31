# -*- coding: utf-8 -*-
# Part of translation_missing_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Missing Translations Report',
    'version': '15.0.1.0.0',
    'summary': 'Find every term still untranslated in an installed language, '
               'grouped by module and by kind, with a count per module.',
    'description': """
Running Odoo in a second language always leaves gaps: a menu here, a field
label there, a report heading nobody exported. Finding them means clicking
around the interface in that language until something looks wrong.

This module adds an administrator report that answers the question directly.
Pick an installed language and it lists the terms that still have no
translation - and, optionally, the ones whose "translation" is character for
character the same as the source - grouped by module and by kind (menu, field
label, selection value, model name, action, report, view / QWeb template,
access group, record content), with a count per module so you know where the
work actually is.

It reads the translation storage of the Odoo version it runs on:

* 14.0 and 15.0 keep every term in the ir.translation table, so on those
  versions the report also lists untranslated Python / JavaScript source terms.
* 16.0 removed that model and moved translations into jsonb columns on the
  records themselves. Source-code terms are no longer stored in the database
  there, so they cannot be listed; structured fields (view architectures, HTML)
  are reported per record and field instead of term by term.

The report states which storage it used and exactly what it can and cannot see
on the running version - it never pretends the two are identical.

Strictly read-only: it never creates, changes or deletes a translation, and
never touches your records. Counts come from grouped SQL queries, the list of
terms is capped by a limit you set and the report says when it truncated.
Available to Settings / Administration users only.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/translation_missing_report_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
