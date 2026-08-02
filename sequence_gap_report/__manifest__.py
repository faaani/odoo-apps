# -*- coding: utf-8 -*-
# Part of sequence_gap_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Sequence Gap Report',
    'version': '16.0.1.0.0',
    'summary': 'Find and explain missing numbers in invoice, order or picking sequences.',
    'description': """
"Why does invoice number 42 not exist?" Auditors and tax authorities ask that
question every year, and Odoo has no answer built in: sequences leave holes
whenever a draft is deleted or a document is discarded.

This module adds a read-only wizard that scans any numbered field of any model
- journal entries and invoices, sales orders, purchase orders, transfers - and
lists every missing number, grouped by numbering series, together with the
document that comes just before and just after the hole, so the gap can be
explained on the spot.

Nothing is ever created, modified or renumbered.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Accounting',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/sequence_gap_report_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
