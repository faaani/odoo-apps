# Add and Remove Tags in Bulk

Tag many records at once from the Action menu — without losing the tags that are
already there.

Odoo lets you tag one record at a time. This module adds an **Add / Remove Tags**
entry to the Action menu of the list views of every model that has tags: select
the records, type the tags to add and the tags to remove, and apply the whole
thing in one step.

## What it does

- **Adds and removes single tags.** The tag set of a record is never replaced, so
  tags a colleague added, and tags you did not mention, are kept exactly as they were.
- **Works on any model that has tags.** Tag fields are detected at runtime:
  contacts, leads, projects and tasks, events, meetings, campaigns — products too
  on Odoo 16.0 and later, where Odoo added product tags — and any custom model
  with a tag field of your own.
- **Lets you choose the field** when a model has more than one tag field, and
  preselects it when there is only one.
- **Shows the tags that already exist** on the chosen tag model.
- **Creates missing tags only if you ask.** The option is off by default: an unknown
  tag name stops the run with a clear message instead of silently creating a typo.
- **Respects access rights.** Records you may not write are skipped and counted; the
  module never elevates your rights to force a change through.
- **Reports what really happened**: records updated, records that already had the
  right tags, records skipped.

## Installation

1. Copy the `bulk_tag_manager` folder into your Odoo add-ons path.
2. Open *Apps*, click *Update Apps List*.
3. Search for *Add and Remove Tags in Bulk* and click *Install*.

## Configuration

1. Nothing to configure: on installation the module scans the models of your
   database and adds the Action-menu entry to those that have a tag field.
2. If you install another app afterwards (CRM, Sales, Project, ...), open *Apps*,
   find *Add and Remove Tags in Bulk* and click *Upgrade*. The scan runs again and
   the new models get the entry too.
3. Every internal user can use the wizard. What they may actually change is decided
   by their normal access rights on the records and on the tags.

## Usage

1. Open a list view — Contacts, Leads, Products, Tasks, ...
2. Tick the records you want to tag.
3. Open the *Actions* menu and choose *Add / Remove Tags*.
4. Pick the tag field if the model has more than one.
5. Type the tags to add and the tags to remove, separated by commas. Matching is
   case-insensitive; the existing tags are listed at the bottom of the dialog.
6. Tick *Create Missing Tags* if a tag you want to add does not exist yet.
7. Click *Apply*.

## Good to know

- Tags are entered by name, not picked from a dropdown: the tag model changes with
  the model you are standing on, and Odoo cannot bind one selection widget to
  several models. The dialog lists the existing tag names to make this easy.
- If two tags of the same model share the same name, the module refuses the run
  rather than guessing which one you meant.
- Only tag fields are offered: a many2many named like a tag field (`tag_ids`,
  `category_id`, `product_tag_ids`, ...) or one pointing at a model named like a
  tag model (`crm.tag`, `res.partner.category`, ...). Other many2many fields —
  taxes on a product, for example — are never listed and are refused server-side
  even if the request is forged, so this wizard can never become a blind mass
  editor. A custom tag field is picked up automatically as long as it follows one
  of those two naming conventions.
- Nothing is ever deleted: removing a tag from a record does not delete the tag
  itself, and no record is archived or unlinked by this module.
- Each record is written on its own, so one record refusing the change never rolls
  back the ones that already went through. Very large selections are processed
  record by record and can take a moment.

## Supported versions

Odoo 14.0, 15.0, 16.0, 17.0, 18.0 and 19.0 — Community and Enterprise. Depends on
`base` only.

## Support

- Email: f.ashraf.dev1@gmail.com
- Author: Farhan Ashraf — https://github.com/faaani/odoo-apps
- License: LGPL-3
