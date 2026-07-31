# -*- coding: utf-8 -*-
# Part of attachment_link_checker. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Check Attachment Files',
    'version': '18.0.1.0.0',
    'summary': 'Find attachments whose file is missing from the filestore, grouped by model.',
    'description': """
After a database restored without its filestore, a half-finished migration or a
botched backup, ``ir.attachment`` rows keep pointing at files that are simply
not on the disk any more. Odoo says nothing about it: the damage only surfaces
the day a user clicks Download and gets an error.

This module adds an administrator scan that walks every filestore-backed
attachment and verifies that its file really exists, that its size still
matches the size recorded in the database and - as an opt-in, because it reads
every byte - that its SHA1 checksum still matches too.

The result is a report of the broken attachments grouped by model, each one
with the record it belongs to, the user who uploaded it, the upload date, the
size that was lost and the exact filestore path that could not be read.

Attachments stored inside the database (``db_datas``) and URL attachments hold
no file on disk, so they are counted separately and excluded from the disk
check. The scan reads the attachment table in batches and never loads a file's
content into memory unless checksum verification is switched on.

Odoo hides from every attachment search the attachments whose linked record
belongs to a model the current user may not read, so a scan run by a Settings
administrator without the Accounting or HR groups would silently skip those
files. Rather than leave that gap invisible, every report counts what it was
not allowed to examine and says so.

The scan is report-only: it never deletes an attachment, because a restore may
still bring the missing files back. An optional cleanup lets you tick individual
rows and delete those dangling records after an explicit confirmation; it
re-checks the disk first and refuses any row whose file has reappeared.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/attachment_link_check_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
