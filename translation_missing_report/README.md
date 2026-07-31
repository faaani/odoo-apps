# Missing Translations Report

Find every term that is still untranslated in an installed language — grouped by
module and by kind, with a count per module so you know where the work is.

Running Odoo in a second language always leaves gaps: a menu here, a field label
there, a report heading nobody exported. Finding them normally means clicking
around the interface in that language until something looks wrong. This module
adds an administrator report that answers the question directly.

Free and open source (LGPL-3). Supported on Odoo 14.0, 15.0, 16.0, 17.0, 18.0
and 19.0. Depends on `base` only.

## What it reports

* Terms with **no translation** in the chosen language.
* Optionally, terms whose translation is **identical to the source** — usually a
  term nobody has looked at yet. Off by default, always counted separately.
* Grouped **by module** (from the record's external ID) and **by kind**: menu
  item, field label / help, selection value, model name, action name, report,
  view / QWeb template content, access group, record content, and — on 14.0 /
  15.0 only — Python / JavaScript source term.
* Per module and kind: reported terms, terms not translated, terms identical to
  the source, terms scanned, and the share already translated.

## The Odoo version difference, stated plainly

Translations are not stored the same way on every series, and this module does
not pretend they are:

* **14.0 and 15.0** keep every term as a row of `ir.translation`. There, the
  report **also lists untranslated Python / JavaScript source terms**, with
  their module.
* **16.0 and later** removed that model and moved translations into JSONB
  columns on the records themselves. Source-code terms are no longer stored in
  the database on those versions — they are read from the module `.po` files at
  runtime — so **they cannot be listed**. The report says this on screen rather
  than silently reporting less.
* **Structured fields** (view architectures, HTML fields) are reported per
  record and field with a preview of the source, not term by term. On 14.0 /
  15.0 such a record counts as translated as soon as one of its terms is
  translated.

The report shows which storage it used (`Translation Storage`) and repeats the
limitations of the running version on its **Coverage** tab.

## Guarantees and limits

* **Strictly read-only.** The report never creates, changes or deletes a
  translation, and never modifies your records. It only writes its own
  temporary result rows, which Odoo cleans up automatically.
* **Counts come from grouped SQL queries** — one aggregate query per
  translatable column, never a record-by-record loop.
* **The list of terms is capped** by the *Listed Terms Limit* you set (default
  500, maximum 20 000). Counts per module are never capped; when the list is
  truncated the report says so and tells you how many terms it left out.
* **Counts are database-wide, the listing is access-checked.** Listed terms are
  filtered through the standard access rules of each model, so a record you are
  not allowed to read is counted but never displayed — the report tells you how
  many were withheld.
* **Records with no external ID** (records your users created) have no module
  and are grouped under `(user data)`.
* **Administrator only** — the report and its results are restricted to the
  Administration / Settings group.
* A language that is **not installed** is refused with a clear message, and so
  is the source language `en_US`, which by definition has nothing to translate.

## Installation

1. Copy the module into your addons path, or install it from the Apps list.
2. Open **Apps**, remove the "Apps" filter, search for *Missing Translations
   Report* and click **Install**.
3. Only the standard `base` module is required.

## Configuration

1. No configuration is needed — the report works as soon as the module is
   installed.
2. At least one language other than the source language must be **installed**
   (Settings → Translations → Languages).
3. Access is restricted to the **Administration / Settings** group.
4. Optional: raise the *Listed Terms Limit* if you want a longer list in one go.

## Usage

1. Go to **Settings → Missing Translations**.
2. Choose the **language** to audit and a **scope**: user interface only,
   business record content only, or everything.
3. Tick *Report terms identical to the source* if you also want terms that were
   "translated" with the source text.
4. Click **Generate Report**.
5. Read **Per Module** to see where the work is, then **Terms** for the
   individual terms.
6. Click **Open Terms List** for the full list grouped by module — filter by
   kind, then select all and **Export** to hand a spreadsheet to your
   translator.
7. Translate the terms with Odoo's own tools, then run the report again to
   watch the counts drop.

## Support

Questions, bugs or feature requests: **f.ashraf.dev1@gmail.com** — I read and
answer every message.

License: LGPL-3.
