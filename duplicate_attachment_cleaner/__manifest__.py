# -*- coding: utf-8 -*-
# Part of duplicate_attachment_cleaner. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Find Duplicate Attachments',
    'version': '14.0.1.0.0',
    'summary': 'Report identical attachments grouped by checksum and remove the redundant copies safely.',
    'description': """
The same quotation PDF gets emailed, re-attached and re-uploaded dozens of
times. Odoo keeps every copy as its own attachment record, so the attachment
table, the exports and the backups keep growing with bytes you already have.

This module adds a scan that groups attachments by the checksum Odoo already
stores, and reports every group of identical files: how many copies exist, how
much space the redundant copies account for, and which records they are
attached to.

By default it only groups copies attached to the SAME record, so removing the
extra ones can never leave a record without its file. Looking for identical
files anywhere in the database is a second, clearly labelled option.

Nothing is ever deleted by the scan. Clean-up is a second, explicitly confirmed
step that keeps the OLDEST copy of every group and removes only the extra ones.
Attachments of the framework models ir.ui.view, ir.asset, ir.actions.report and
ir.module.module, attachments that hold a binary field of a record, and empty
files are excluded from both the report and the clean-up.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/duplicate_attachment_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
