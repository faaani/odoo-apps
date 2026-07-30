# -*- coding: utf-8 -*-
# Part of attachment_upload_guard. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Attachment Upload Guard',
    'version': '14.0.1.0.1',
    'summary': 'Block risky file types and oversized attachments — a size and extension policy Odoo does not ship.',
    'description': """
Odoo lets users attach anything, of any size: executables, scripts and
half-gigabyte videos end up in your database and backups.

This module adds a simple upload policy — a blocked extension list and a
maximum file size — enforced on every attachment a user creates, with a clear
error message. System-generated attachments (reports, assets, imports) are
never blocked.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base_setup'],
    'data': ['views/res_config_settings_views.xml'],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
