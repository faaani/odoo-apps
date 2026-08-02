# -*- coding: utf-8 -*-
# Part of record_rule_tester. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Record Rule Tester',
    'version': '18.0.1.0.0',
    'summary': 'Pick a user and a model and see which record rules apply, how many records they can reach, and why one record is hidden.',
    'description': """
"Why can't this user see that order?" is normally answered by opening
Settings / Technical / Record Rules, reading a few domains full of
``user.company_id`` and guessing. This module answers it by asking the server.

How it works
------------
Pick a user, pick a model, press Run Test. The wizard runs the searches **as
that user** - ``self.env[model].with_user(user)`` - so the numbers come out of
Odoo's own rule engine, not out of a re-implementation of it.

What you get
------------
* **Applicable record rules**, global ones and group ones listed separately,
  with the operations each covers, the groups of the tested user it is attached
  to, and its domain. Global rules are ANDed with everything else; group rules
  are ORed with each other, and the screen says so.
* **Per operation**: whether an access control line grants read / write /
  create / delete on the model at all, how many record rules apply, and how
  many records the user can actually reach.
* **A verdict on one record**: type a record id and get "can read" or "cannot
  read" - and when it is "cannot read", the rules that exclude it, taken from
  ``ir.rule._get_failing()``, the very routine Odoo uses to name rules in its
  own error messages.
* **A comparison figure**: the same count taken for you, the administrator
  running the test, so a restricted user's number is immediately meaningful.

Honest limitations
------------------
* Domains are displayed **exactly as stored**. ``user.company_id`` and friends
  are not expanded into values; the evaluated result is what the counts and the
  verdict report, and the screen repeats that where it matters.
* Counts stop at a cap (10 000 by default, adjustable up to 200 000). A count
  that reached the cap is flagged as capped, so it reads as "this many or
  more", never as an exact total.
* The Write and Delete counts are records the user can **both see and**
  write/delete: a search always applies the read rules on top of the operation's
  rules. Create has no count at all - create rules validate the values of a new
  record, they do not filter existing ones - and the screen says so instead of
  showing a meaningless zero.
* Rules that Odoo inherits from a parent model through ``_inherits`` (say
  ``product.product`` reaching ``product.template``) are applied by the server
  but are not listed here; a note tells you to run the test on the parent model.
* Counts are taken with every company the tested user is allowed to access
  enabled, and with archived records included. The companies used are shown.
* Field-level access (``groups=`` on a field) and menu visibility are not
  covered - this is about record rules and model access.
* Testing the superuser reports what an ordinary user with the same groups
  would see: in real operation the superuser bypasses rules entirely, and a
  note says so.

Read-only and admin-only
------------------------
The tester only ever runs searches. It never writes to ``ir.rule`` or
``ir.model.access``, never creates, edits or deletes a rule, and never calls
``sudo()`` to widen what it is measuring. A model the tested user has no access
to is reported as "no access" rather than raising. Every screen and every model
is restricted to Settings / Administration users.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/record_rule_tester_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
