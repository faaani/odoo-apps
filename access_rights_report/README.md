# Access Rights Matrix

A read-only audit matrix over `ir.model.access` and `ir.rule`: one row per model
and group with read / write / create / delete ticks, filters by model, by group
and by permission, the effective rights of a group once inherited groups are
resolved, and the record rules with their domains.

Free and open source (LGPL-3). Odoo 14.0, 15.0, 16.0, 17.0, 18.0 and 19.0.

## Why

Answering "which groups can delete invoices?" in standard Odoo means opening
Settings → Technical → Access Rights and paging through the list one line at a
time. This module turns those lines into something you can filter, group and
export.

## What you get

Three reports under **Settings → Users & Companies → Access Rights Matrix**:

* **Access Rights Matrix** — one row per model and group. When several modules
  add an access line for the same pair they are merged the way Odoo merges them:
  a permission is granted as soon as one active line grants it. The row shows how
  many lines it merged and a compact `RWCD` code.
* **Rights by Group** — every model a group can reach, including the rights it
  inherits from the groups it implies (resolved transitively) and the rights every
  user gets from access lines that carry no group. Each row says whether the right
  is direct, inherited or global, and names the groups that supply it.
* **Record Rules Report** — every `ir.rule` with its domain, the operations it
  applies to, whether it is global or attached to groups, and which groups.

Filters ship for each permission ("grants Delete", "grants Create", …), for
"Full Access", "Read Only" and "Grants Nothing", for global access lines, for
models with no access line at all, and for wizards and abstract models. Group by
model or by group and export either shape.

## Installation

1. Copy the module into your addons path, or install it from the Apps list.
2. Open **Apps**, remove the "Apps" filter, search for *Access Rights Matrix* and
   click **Install**.
3. Only the standard `base` module is required.

## Configuration

1. No configuration is needed; the reports work as soon as the module is
   installed.
2. Access is restricted to the **Administration / Settings** group. No other user
   can read the reports, and there is no setting to widen that.
3. Developer mode is not required — the menus live under Settings, next to
   Users & Companies.

## Usage

1. Go to **Settings → Users & Companies → Access Rights Matrix**.
2. In **Access Rights Matrix**, type a model in the search bar (for example
   `account.move`) and apply the **Grants Delete** filter to see exactly which
   groups may delete it.
3. Group by **Model** or by **Group**, select all and use **Export** to hand the
   auditor either shape.
4. In **Rights by Group**, expand a group — or select groups in *Users &
   Companies → Groups* and use **Action → Effective Access Rights** — to see
   every model that group reaches and where each right comes from.
5. In **Record Rules Report**, filter by model or group to read the domains that
   decide which records those groups actually see.

## What it does and does not cover

* **Inherited groups.** The matrix is deliberately *literal*: it reports the
  access lines exactly as recorded and does **not** expand implied groups.
  **Rights by Group** is the report that expands them — it walks
  `res.groups.implied_ids` transitively (a cycle in the implication graph
  terminates instead of looping) and adds the access lines that carry no group,
  because Odoo grants those to every user.
* **Active lines only.** An unticked access line is ignored by Odoo, so it is
  ignored here. Record rules are listed whether enabled or not; disabled ones are
  hidden behind the default *Active* filter.
* **Models with no access line** are listed with a *No Access Rule* flag rather
  than hidden: nobody but the superuser can reach them. Abstract models (mixins,
  report templates) store nothing and never need a line, so they are hidden by
  the default *Stored Models* filter.
* **Not covered:** field-level access (the `groups` attribute on a field), menu
  and view visibility, and rights a user gains from a company or from `sudo` in
  custom code.
* **Size.** *Rights by Group* expands to one row per group per reachable model.
  On a large database with many apps installed that is in the order of a hundred
  thousand rows, and a database view carries no index, so the first load and a
  full export take a few seconds. The matrix itself stays small — a few thousand
  rows.
* **Nothing is modified.** The three reports are SQL views. The module never
  creates, edits, disables or deletes an access line or a record rule, never uses
  `sudo`, and the reports refuse create, write and delete even for
  administrators.

## Support

Questions, bugs or feature requests: **f.ashraf.dev1@gmail.com**

License: LGPL-3.
