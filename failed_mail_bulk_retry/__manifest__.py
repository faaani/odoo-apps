# -*- coding: utf-8 -*-
# Part of failed_mail_bulk_retry. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Retry Failed Emails in Bulk',
    'version': '14.0.1.0.0',
    'summary': 'Admin screen listing every email Odoo failed to deliver, with bulk retry, retry-since-date and bulk cancel.',
    'description': """
After an SMTP outage, hundreds of messages sit in the Odoo mail queue in
"Delivery Failed" state. Standard Odoo can only cure them one at a time: open
the message, click Retry, go back, open the next one.

This module adds an administrator screen that lists the failed messages with
their subject, recipient, age and the exact error the mail server returned, and
lets you act on them in bulk:

* retry the messages you tick,
* retry everything that failed on or after a date you choose,
* cancel the messages that should never go out.

Every run reports how many messages were put back in the queue, how many were
delivered, how many failed again immediately and how many were skipped, so you
know whether the mail server is really fixed.

Only messages in "Delivery Failed" state are ever touched. Sent, pending
(Outgoing) and already Cancelled messages are never modified. Re-sending uses
Odoo's own Retry and Send code path, message by message inside its own
savepoint, so one bad recipient address cannot abort the rest of the batch.

Restricted to Settings / Administration users.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Technical',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/failed_mail_retry_wizard_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
