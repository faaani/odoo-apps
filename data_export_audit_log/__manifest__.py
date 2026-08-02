# -*- coding: utf-8 -*-
# Part of data_export_audit_log. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Export Audit Log',
    'version': '17.0.1.0.0',
    'summary': 'Audit trail of data exports: who exported which records, from which model, with which fields, and when.',
    'description': """
Export rights in Odoo are all-or-nothing: a user either has the "Allow Export"
group or not, and once they have it there is zero trace of what left the
database. This module records every export made through Odoo's standard export
path (the list-view export dialog, CSV and XLSX downloads - anything that calls
Model.export_data) in a read-only audit log:

* who exported (user),
* which model (technical name and label),
* how many records,
* the exact list of exported fields,
* when.

Odoo internally exports grouped lists group by group and very large lists in
batches; those chunks are coalesced into a single log entry per export, so
the record count is the real total, not a fragment.

The log lives under Settings > Export Audit Log and is visible to
Settings / Administration users only. Log rows cannot be created or edited from
the user interface by anyone - they are written exclusively by the export hook -
so the trail cannot be forged. Administrators may delete rows, and a daily
scheduled action purges entries older than a configurable retention period
(180 days by default, configurable in Settings; 0 keeps logs forever).

Logging is fail-safe by design: if writing the audit row fails for any reason,
the export itself still succeeds and a warning is written to the server log.

Honest limitations: this logs the standard export path only. It does not capture
report PDF downloads, raw RPC/API reads (e.g. search_read), or database-level
dumps. Combine it with a restrictive "Allow Export" group policy for real
coverage of data leaving your system.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'views/export_log_views.xml',
        'views/res_config_settings_views.xml',
        'data/ir_cron_data.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
