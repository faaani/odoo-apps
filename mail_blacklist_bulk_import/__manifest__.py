# -*- coding: utf-8 -*-
# Part of mail_blacklist_bulk_import. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Bulk Import Email Blacklist',
    'version': '14.0.1.0.0',
    'summary': 'Blacklist or un-blacklist hundreds of email addresses at once from pasted text or a CSV/TXT file.',
    'description': """
Odoo's Email Blacklist is a one-address-at-a-time screen. After a bounce
report, a complaint list or a GDPR erasure request, an administrator is left
pasting addresses one by one.

This module adds a bulk wizard next to the standard blacklist screen, under
Settings > Technical > Discuss (developer mode), and in the Action menu of the
Blacklisted Email Addresses list:

* Paste addresses (one per line, or separated by commas or semicolons) or
  upload a CSV/TXT file.
* Choose the mode: add the addresses to the blacklist, or remove them from it.
* Every address is normalized and validated first; whitespace, mixed case and
  "Name <address@example.com>" forms are handled.
* A per-address report tells you exactly what happened: added, already
  blacklisted, removed, not blacklisted, duplicated in the input, or invalid
  with the reason why.
* The invalid addresses are handed back as plain text so they can be fixed and
  re-submitted in one click.

Blacklisting uses Odoo's own mail.blacklist helpers, so the standard chatter
entry is logged on each blacklist record. One bad line can never abort the run:
each address is processed in its own savepoint.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Marketing/Email Marketing',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/mail_blacklist_bulk_import_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
