# -*- coding: utf-8 -*-
# Part of attachment_bulk_download. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Download Attachments in Bulk',
    'version': '17.0.1.0.0',
    'summary': 'Select records and download all of their attachments as a single ZIP file.',
    'description': """
Odoo downloads files one at a time. Collecting the signed contracts of thirty
customers, or every document attached to a batch of records, means opening
thirty forms and clicking thirty times.

This module adds a "Download Attachments" action to the Action menu: select the
records, see how many files and how many megabytes that represents, and get
them all back as one ZIP.

Files are stored in the archive as "<record name>/<file name>", so two records
with an identically named document never overwrite each other. Attachments the
user is not allowed to read are silently left out instead of breaking the
download, and a configurable size limit (200 MB by default) refuses archives
that would be too large for the server to build.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/attachment_bulk_download_wizard_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
