# Menu Visibility by Group

Who sees each back end menu item — and how to change it, without developer mode.

Hiding a menu from a group today means turning on developer mode, opening
*Settings / Technical / User Interface / Menu Items*, finding the item and editing
a Groups field with no idea who could see it before, or who can see it now. This
module replaces that with one screen.

Free and open source (LGPL-3). Odoo 14.0, 15.0, 16.0, 17.0, 18.0 and 19.0.

## What you get

* **The whole menu tree on one page**, every item under its own parent, with its
  full path.
* **Groups editable in the list** — click the Groups cell, add or remove a group,
  save.
* **A plain answer per item**: *Members of Sales / Administrator*, or *Everyone
  (no group on this item) + the parent menu Reporting needs Sales / Administrator
  + read access on sale.report*.
* **Inherited restrictions made visible** — a *Restricted By* column saying
  whether the limit comes from the item, from a parent menu, or from both.
* **Bulk add / remove** — select several items, *Actions → Add / Remove Groups*,
  optionally down the whole sub-tree, with a count of what will really change.
* **Preview a user menu** — pick a user, get the items they really see and, for
  everything else, the reason.
* **The caches are cleared for you** after every change, including a change
  written from the group side (`res.groups` → Access Menu).

## How "who sees this menu" is worked out

Odoo hides a back end menu item for three different reasons, and this screen
reports all three — only the first is visible in the standard form:

1. **The groups on the item.** A user in none of them never sees it. An item with
   no group puts no restriction of its own.
2. **The groups on a parent menu.** A menu item is only ever drawn inside its
   parent, so a user shut out of the parent never reaches the child, even though
   nothing on the child says so. The column names the parent and its groups.
3. **Read access on the action's model.** When an item carries an action, Odoo
   hides it from anybody who cannot READ the model that action opens, whatever
   groups the item carries. The screen names the model and the groups an access
   control line grants read on it.

A folder is a fourth case, handled by Odoo itself: a menu with no action is only
drawn when at least one item below it is visible.

The preview does not re-implement any of this. It calls
`ir.ui.menu._visible_menu_ids()` evaluated as the chosen user — Odoo's own
routine — and then applies the parent-chain rule the web client applies when it
builds the menu tree.

## Installation

1. Copy the module into your addons path, or install it from the Apps list.
2. Open **Apps**, remove the "Apps" filter, search for *Menu Visibility by Group*
   and click **Install**.
3. Only the standard `base` module is required.

## Configuration

1. No configuration is needed — both screens work as soon as the module is
   installed.
2. Access is restricted to the **Administration / Settings** group
   (`base.group_system`), the group Odoo itself requires to write a menu item.
   That covers the screens, the models *and* every field this module adds: a
   user outside the group cannot even read back the answers.
3. Developer mode is **not** required: the two menu entries sit under Settings,
   not under the Technical menu.

## Usage

1. Go to **Settings → Users & Companies → Menu Visibility**.
2. Find the item — type part of its name, or filter on *Restricted To Groups* /
   *No Group (Everyone)*, or group by parent menu.
3. Read the **Who Sees This Menu** column; open the item for the full reasoning,
   including the parent menu and the action model.
4. To change it: edit the **Groups** cell in the list, or tick several rows and
   use **Actions → Add / Remove Groups**. Tick *Also apply to every item below*
   to hit a whole sub-tree.
5. Check the result with **Settings → Users & Companies → Preview A User Menu**:
   pick the user, press *Show This User's Menu*, and switch *Show* between what
   they see, what is hidden, and everything.
6. Your own menu bar is drawn from a cache too. After a change that affects you,
   use the **Reload Interface** button on the result screen (or press F5).

## Limitations, stated up front

* It covers **back end menu items** (`ir.ui.menu`). Website menus, portal pages,
  buttons inside a form and fields hidden by `groups=` are different mechanisms
  and are not touched.
* The preview is computed with **developer mode off**. An administrator browsing
  with developer mode on sees the extra technical items on top of what the
  preview lists, and the Notes tab says so.
* Groups placed on the **action record itself** are not part of Odoo's menu
  visibility computation, so they are not part of the answer.
* The screen **edits menu visibility only**. It never creates, renames or deletes
  a menu item, never changes a user's group membership, and never edits an access
  right or a record rule.
* Removing the last group from an item makes it visible to everyone who can reach
  its parent — that is what "no group" means in Odoo. The wizard counts those
  items and warns before you apply.
* In a **multi-worker** deployment the other workers pick the cache invalidation
  up when the transaction commits, through the registry signalling Odoo already
  uses for it — not instantly, but without a restart.
* The preview lists up to 3 000 menu items and says so if it had to stop there;
  the counters stay exact.
* Items are listed **under their parent**, but sibling items come out in database
  order rather than in the sequence order the real menu bar uses. Add the
  optional *Sequence* column and sort on it if that matters to you.
* The **Menu Path** column stops at six levels and ends in `...` beyond that — it
  uses Odoo's own path builder, which has that limit.
* If this screen ever cannot read a menu's action, it says so on the line instead
  of reporting the item as a folder. It never turns "I could not check" into
  "there is nothing to check".
* On **Odoo 19.0** the field is called `group_ids` instead of `groups_id`; the
  module reads the name from the registry, so it behaves identically on all six
  series.

## Support

Questions, bugs or feature requests: **f.ashraf.dev1@gmail.com** — I read and
answer every message.

License: LGPL-3.
