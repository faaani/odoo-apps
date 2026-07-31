# -*- coding: utf-8 -*-
# Part of menu_access_visibility. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
{
    'name': 'Menu Visibility by Group',
    'version': '16.0.1.0.0',
    'summary': 'See which groups can see each back end menu item, change them from one screen, and preview the menu of any user.',
    'description': """
Hiding a menu from a group today means turning on developer mode, opening
Settings / Technical / User Interface / Menu Items, finding the item, and
editing a Groups field with no idea who could see it before or who can see it
now. This module replaces that with one screen.

The menu list
-------------
Every back end menu item, in tree order, with:

* the **groups recorded on the item** - editable straight from the list, one
  cell per item;
* **Restricted By**: everyone, the groups on the item, a parent menu, or both;
* **Who Sees This Menu**: a plain sentence, not a list of technical ids;
* the **model the item's action opens** and the groups an access control line
  grants read on it.

How "who sees this menu" is worked out
--------------------------------------
Odoo hides a menu item for three different reasons, and the screen reports all
three, because only the first one is visible in the standard Menu Items form:

1. **The groups on the item.** Empty means no restriction of its own.
2. **The groups on a parent menu.** A menu item is only ever drawn inside its
   parent, so a user shut out of the parent never reaches the child - even
   though nothing on the child says so. The column names the parent and its
   groups.
3. **Read access on the action's model.** When an item carries an action, Odoo
   hides it from anybody who cannot read the model that action opens,
   *whatever groups the item carries*. The screen names the model and the
   groups that have read on it.

Changing the groups
-------------------
Edit the Groups cell in the list, or select several items and use
**Action / Add / Remove Groups** to add or take away a group across many items
at once - optionally down the whole sub-tree. Before applying, the wizard says
how many items will really change and how many will be left with no group at
all, which is what makes an item visible to everybody again.

Menus are answered from a cache keyed on the user's groups, so **the caches are
cleared for you** after every change. Without that the change looks like it did
nothing until the server is restarted - the single most common surprise when
editing menu groups by hand.

Preview a user menu
-------------------
Pick a user and get their menu: what they really see, and for everything else
the reason - "limited to Sales / Administrator and the user is in none of
them", "no read access on account.move", "the parent menu Accounting is hidden
from this user". The visible set comes from
``ir.ui.menu._visible_menu_ids()`` evaluated as that user: Odoo's own routine,
not a copy of its rules.

Honest limitations
------------------
* It covers **back end menu items** (``ir.ui.menu``). Website menus, portal
  pages and buttons inside a form are a different mechanism and are not
  touched.
* The preview is computed with **developer mode off**. An administrator with
  developer mode on sees the extra technical items on top of what is listed.
* Groups on the *action* record itself are not part of Odoo's menu visibility
  computation, so they are not part of the answer; what counts for an action
  menu is read access on its model, and that is what is reported.
* The screen **edits menu visibility only**. It never creates or deletes a menu
  item, never renames one, never changes a user's group membership, and never
  edits an access right or a record rule.
* Sibling items are listed under their parent but in database order, not in the
  sequence order the real menu bar uses; an optional Sequence column is there to
  sort on. The Menu Path column stops at six levels, the limit of Odoo's own
  path builder.
* When the screen cannot read a menu's action it says so on the line, instead of
  reporting the item as a folder. "I could not check" never renders as "there is
  nothing to check".
* Everything is restricted to **Administration / Settings**
  (``base.group_system``), the group Odoo itself requires to write menu items -
  the screens, the models, and every field this module adds.
""",
    'author': 'Farhan Ashraf',
    'website': 'https://github.com/faaani/odoo-apps',
    'category': 'Tools',
    'license': 'LGPL-3',
    'support': 'f.ashraf.dev1@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/ir_ui_menu_views.xml',
        'wizard/menu_visibility_preview_views.xml',
        'wizard/menu_group_update_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
