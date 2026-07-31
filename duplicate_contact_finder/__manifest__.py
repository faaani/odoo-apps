# -*- coding: utf-8 -*-
# Part of duplicate_contact_finder. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Find Duplicate Contacts',
    'version': '14.0.1.0.0',
    'summary': 'Read-only scan grouping probable duplicate contacts by email, phone or name, with a link to Odoo\'s merge wizard.',
    'description': """
Every long-lived Odoo database ends up with the same customer entered three
times: once by the salesperson, once by the website, once by an import.

This module adds an administrator scan that finds those contacts and shows them
grouped, so you can decide what to do with each cluster:

* same **email** (trimmed, case-insensitive),
* same **phone or mobile** - compared on digits only, so "+33 1 23 45 67 89",
  "0033123456789" and "01 23 45 67 89" land in the same group, and a phone is
  compared against other contacts' mobiles too,
* same **name** - ignoring case, accents, punctuation and word order, so
  "Ferreira, Jose", "Jos? Ferreira" and "jose  ferreira" match.

Each criterion can be switched off independently, and you choose whether to
scan companies, individuals or both, whether to include archived contacts, and
whether to include the invoice/delivery addresses attached to a company.

Every group shows its members with their creation date, phone, email, whether
the contact has a login, and how many records are linked to it (messages,
activities, child contacts, invoices, orders, leads, transfers, tasks) so the
one to keep is obvious at a glance.

**Nothing is ever merged, edited, archived or deleted by this module.** Merging
rewrites foreign keys and destroys records, and Odoo already ships a wizard for
it: each group has a button that opens Odoo's standard Merge Contacts wizard
with exactly those contacts pre-selected, where you pick the destination
contact and confirm.

The whole scan is a handful of grouped SQL statements - the contact table is
never read record by record - and the number of reported groups is capped, with
a clear warning when the result was truncated.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['contacts'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/duplicate_contact_finder_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
