# -*- coding: utf-8 -*-
# Part of user_permission_diff. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Compare User Permissions',
    'version': '18.0.1.0.0',
    'summary': 'Side by side comparison of two users groups, with a confirmed one-way copy of the missing ones.',
    'description': """
"Give the new hire the same rights as Maria" means opening two user forms side
by side and comparing tick boxes - and the tick boxes lie, because a group can
be granted by another group that implies it. This module answers the question
properly.

What you get
------------
* **Three columns** - the groups only User A has, the groups only User B has,
  and the groups they share, in one screen.
* **Effective groups by default** - every group the user is assigned, plus every
  group those imply, transitively. That is what Odoo really checks when it
  decides whether a menu is visible or a button is allowed. Each line says
  whether the user has the group because it is *Assigned* on their form or
  because it is *Implied* by another group.
* **Assigned only** - a second mode that lists just the boxes ticked on the user
  form, for when you are about to edit them. The column headers always say which
  of the two you are looking at.
* **What the difference actually grants** - a table of the models one user can
  read, write, create or delete and the other cannot, computed from the access
  control lines of the effective groups of both.
* **A one-click copy, behind a confirmation** - "copy the missing groups from A
  to B" opens a dialog that names the target, lists every group that will be
  added, and refuses to do anything until you tick the confirmation box.

The copy is deliberately narrow
-------------------------------
* It only ever **adds**. Groups are written with link commands, never with a
  replace command, so User B keeps every group they already have. Nothing is
  removed, ever, and if a write were to remove anything the module aborts and
  changes nothing.
* Only the groups User A is **assigned** are written - the implied ones follow
  from them. That is the smallest write that closes the gap, and it keeps
  User B's form readable afterwards.
* **The superuser (id 1) and the default administrator account are refused as
  targets.** They are the accounts you cannot afford to change by accident.
* The list of groups is **recomputed on the server** when you press Grant, from
  the two users themselves, so a payload forged over RPC cannot widen it.
* Your own administrator rights are **checked again at the moment of the write**,
  not only when the dialog was opened.
* What was granted is written in the **chatter** of the target user, naming the
  source user, the groups and who did it.

Honest limitations
------------------
* Groups only. Record rules (ir.rule) and field-level access are not compared,
  and the model table is built from access control lines alone - two users with
  the same groups can still see different *records*.
* The model table is capped at 200 rows per side; when the difference is bigger
  than that the wizard says so on screen rather than truncating silently.
* Multi-company access, which is not a group, is not part of the comparison.
* The copy is not undoable from the wizard: to reverse it, untick the groups on
  the user form. The chatter note tells you exactly which ones were added.
* Reserved to users with Settings / Administration access, in both directions:
  a user without it can neither compare nor copy.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/user_permission_diff_views.xml',
        'wizard/user_permission_diff_copy_views.xml',
        'views/user_permission_diff_menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
