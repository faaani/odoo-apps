# -*- coding: utf-8 -*-
# Part of mail_template_usage_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Email Template Usage Report',
    'version': '18.0.1.0.0',
    'summary': 'Read-only report showing which email templates are actually used: send counts, last used date, customised templates and templates wired to server actions.',
    'description': """
A database that has been live for a while ends up with dozens of email
templates, and nobody can tell which ones still matter. Odoo itself gives you
no answer: core keeps **no link at all** between a sent email and the template
that produced it, on any version from 14.0 to 19.0.

This module adds that link and reports on it.

What the report shows for every template
----------------------------------------
* the model it applies to, its language and whether it is archived;
* whether it came from a module or was created in this database;
* whether it was **customised** after the module that ships it was installed
  (those changes are the ones a cleanup would throw away);
* how many emails/messages were produced from it, when it was **first** and
  **last** used;
* how many of those mails and chatter messages are still stored;
* whether an **automated action / server action** points at it, which makes it
  in use even with zero sends.

Ready-made filters: Never Used, Used in the Last 90 Days, Not Used in 90+ Days,
Customised, Standard, In Use, Unused and Unreferenced, From a Module, Created in
this Database. Group by model, usage, source, language or module.

Honest limitations - please read
--------------------------------
* **Counting starts at installation.** Odoo stores nothing that ties an old
  email back to its template, so emails sent before you install this module can
  never be counted. The "First Used" column tells you when tracking began.
* **Unused does not mean safe to delete.** Templates are also called from Python
  code, from the Python part of server actions and from configuration fields of
  other apps (stages, alarms, website settings). Only server actions and
  activity types are detected here. Always check before deleting a template.
* Detection covers `mail.template.send_mail()`, the Send Message / mass-mail
  composer and automated actions using them. A module that renders a template
  by hand and builds its own email is not detected.

The report is a single read-only SQL view - one grouped query, no per-template
loop - and it never creates, edits or deletes anything.

It is restricted to administrators (Settings) and its menu sits under
Settings > Technical > Email, next to the templates themselves, so developer
mode has to be on for the menu to appear.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Productivity/Discuss',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/mail_template_usage_report_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
