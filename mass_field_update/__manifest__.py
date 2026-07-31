# -*- coding: utf-8 -*-
# Part of mass_field_update. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Update a Field on Many Records',
    'version': '17.0.1.0.0',
    'summary': 'Set the same value on one field of many records at once, with a preview, a confirmation and a per-record report.',
    'description': """
Changing one field on three hundred records means three hundred clicks, or an
export/import round trip that touches columns you never meant to touch.

This module adds an "Update a Field" action to the list view: select the
records, pick the field, type the value with an input that matches its type,
see how many records will actually change, confirm, and apply.

The guards are the point.

* Only fields you may really write are offered: never "active", never a
  password or any other credential-looking field, never a read-only field nor
  a computed one Odoo does not let you edit.
* The field is validated again against the model and against your access
  rights at apply time, so a forged field name is refused.
* Records you may not write are skipped and counted. Nothing is ever written
  with elevated privileges.
* Every record is written in its own savepoint, so one failure does not roll
  back the batch.
* A note is logged in the chatter of each changed record, on models that have
  one.
* The result reports updated / skipped / failed, with the reason for each skip.

Reserved to users with Settings access. Up to 10 000 records per run.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/mass_field_update_wizard_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
