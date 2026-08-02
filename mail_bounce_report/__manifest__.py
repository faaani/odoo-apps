# -*- coding: utf-8 -*-
# Part of mail_bounce_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Email Bounce Report',
    'version': '16.0.1.0.0',
    'summary': 'Read-only report of contacts whose emails bounce: bounce count, threshold flag, blacklist status and last bounced message.',
    'description': """
Odoo counts bounces per contact in the standard "Bounce" field
(res.partner.message_bounce) and quietly stops treating an address as usable
once it climbs, but there is no screen anywhere that shows who is bouncing.
A mailing list therefore decays invisibly.

This module adds a read-only report listing every contact that either has a
bounce counter above zero or sits on the email blacklist, with:

* the contact and the exact address stored on it,
* the standard bounce counter,
* an "Above Threshold" flag using an inclusive >= test against a threshold you
  configure in Settings (default 10, the same limit Odoo's own mail code uses),
* the date of the most recent message to that contact that is recorded as
  bounced - Odoo stores no timestamp for the bounce itself, so this is the
  message date, and it is empty when no bounced message survives,
* whether the normalized address is on the active mail.blacklist, and when it
  was put there.

Filters for bounced at all, at or above threshold, below threshold,
blacklisted, not blacklisted, with or without an email address, active or
archived contacts. Group by company, country, blacklist status, threshold
status or bounce month.

The report is a single database view - no per-contact loop and no writes at
all. It never changes a contact, never resets a bounce counter and never adds
or removes a blacklist entry; it only links out to the contact and to the
blacklist. Visible to Settings / Administration users only, and it never shows
a contact the standard Contacts list would hide from that user.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Marketing',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail', 'base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'security/mail_bounce_report_rules.xml',
        'views/mail_bounce_report_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
