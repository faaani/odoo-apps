# Edit Field Labels and Tooltips

Rename any field and write your own tooltip from a simple Settings screen - no developer
mode, no hunting through thousands of technical rows. One click puts the original back.

## What it does

* **Pick a model, see its fields.** Search the model in the search bar; the list shows its
  user-facing fields with the label and the tooltip users see today.
* **Edit in the list.** Type a new label, type a tooltip, save. The change is live
  immediately, for every user, on every form, list and report showing that field.
* **Add a tooltip where there was none** - not only override an existing help text.
* **Reset to the original, exactly.** The first time a field is customized, the label and
  tooltip Odoo shipped are stored; Reset writes those exact values back.
* **Review everything you changed** on a dedicated *Customized Labels* screen, and revert
  several rows at once from the Actions menu.
* **Re-apply after an upgrade**: upgrading the module that owns a field restores its
  built-in label; one click puts your version back.
* **No technical noise**: `create_uid`, `write_uid`, `create_date`, `write_date`,
  `display_name`, `id` and anything starting with an underscore are hidden by default,
  and one filter shows them again.

## Read this before you rename anything

* A label is **shared by every user of the database**. There is no per-user labelling.
* Labels and tooltips are **translatable**. You always edit the language of your own user
  session - the screen shows which one - and the other languages keep their own values.
  To change a French label, switch your own user to French and edit it there.
* The screens are restricted to **Settings administrators** (`base.group_system`).
* A view can override a label in its own XML (`<field name="x" string="..."/>`); that view
  wins over the field label, here as everywhere else in Odoo.

## What is never touched

Only the **label** and the **help text** of a field are ever written. No field is created,
renamed, retyped, moved or deleted, and no business record is read or modified.

Uninstalling removes the module's own table, but the labels you already applied stay
applied - uninstalling is not an undo. Reset what you want back to normal *before*
uninstalling.

## Installation

1. Copy the `field_help_editor` folder into your Odoo addons path.
2. In Odoo, open **Apps** and click **Update Apps List**.
3. Search for **Edit Field Labels and Tooltips** and click **Install**.

## Configuration

1. There is nothing to configure.
2. Make sure the people who should use it have the **Settings** access right
   (Settings / Users & Companies / Users / Administration = Settings).
3. The menu lives in **Settings / Field Labels**. Developer mode is not needed.

## Usage

1. Go to **Settings / Field Labels / Edit Field Labels**.
2. Type the model you are looking for in the search bar (for example *Contact*) and pick
   the **Model** suggestion.
3. Click the **Label** cell of the field you want to rename and type the new label. Click
   the **Tooltip** cell to write the explanation users see when they hover the field. Save.
4. Reload a form showing the field: the new label and tooltip are there for everyone.
5. To undo, click **Reset** on the row (or open the row and use **Reset to Original**).
6. Go to **Settings / Field Labels / Customized Labels** to review every change, revert
   several at once from the **Actions** menu, or **Re-apply** your labels after an Odoo
   module upgrade restored the built-in ones.
7. To see the bookkeeping columns, remove the **Hide Bookkeeping Fields** filter.

## Good to know / limitations

* Upgrading the Odoo module that *defines* a field rewrites that field's label and help
  from its source code, which undoes your change. Nothing is lost: the customization stays
  listed and **Re-apply** puts it back.
* Abstract models, and models your user cannot read, are refused with a clear message.
* On **Odoo 14 and 15** the properties of a built-in field cannot be written at all, so the
  module stores your label and tooltip as a translation entry of the language you are
  editing - the way Settings / Translations does it. Two consequences on those two
  versions: a customization applies strictly to the language you edited (the other
  languages keep showing the built-in label instead of following your English one), and
  emptying a tooltip brings back the field's built-in help text.
* Saving a label clears the label caches - and, on recent versions, reloads the field
  registry - so a save takes a moment on very large databases. Users see the new label
  after their next page load.
* Emptying a tooltip removes your override for the language you are editing; the field
  then shows the tooltip Odoo ships with it (or, in a translated database, the value of
  the source language). The other languages are never touched.
* The module changes how a field's help text is resolved (`Field._description_help`), so
  that a tooltip can be added to a field that has none. On a server hosting several
  databases in one process, the change applies only to the databases where this module is
  installed. For any field you never customize, the text shown stays exactly the one Odoo
  ships.

## Support

* Email: f.ashraf.dev1@gmail.com
* Author: Farhan Ashraf
* License: LGPL-3
* https://apps.odoo.com/apps/modules/browse?author=Farhan+Ashraf
