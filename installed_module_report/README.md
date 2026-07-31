# Installed Modules Report

Before an upgrade or an audit somebody always asks the same three questions: what is actually installed on this database, how much of it is third party, and what breaks if we remove this one? The Apps screen answers none of them well. This module adds a read-only report over the module list with the version, author, licence, origin and dependencies of every installed module.

## Features
- Every installed module in one list: technical name, module name, installed version, author, licence, category and status. Modules that are not installed never appear.
- Origin classification: Odoo S.A. (core), Odoo S.A. (Enterprise), Odoo Community Association (OCA), other third party, or author not declared.
- Direct dependencies and reverse dependencies, as counts you can sort on and as clickable lists.
- Approximate install date, taken from the oldest external ID the module created (Odoo stores no real install date).
- Audit filters: Third Party Only, Non-standard Licence, Installed But Not Part Of Any App, Proprietary Licence, Applications, Auto Installed, Nothing Depends On It, Pending Upgrade Or Removal.
- Group by origin, licence, licence type, author, category, status or install month; export to spreadsheet.
- One SQL view with grouped sub-queries, and one query per page for the dependency lists — never one query per module.
- Read access only, for the Administration / Settings group: the module never installs, upgrades or uninstalls anything and never edits the module list.

## How modules are classified
The report reads the module manifest, so the rules are stated in full:
- Author `Odoo S.A.` (also `Odoo`, `Odoo SA`, `Odoo PS`, `OpenERP`) means Odoo core — or Enterprise when the licence is OPL-1 or OEEL-1.
- An author mentioning `Odoo Community Association` or `(OCA)` means OCA.
- Everything else is other third party; an empty author is reported as author not declared — a bucket that only ever fills on Odoo 19, because up to Odoo 18 Odoo itself substitutes "Odoo S.A." for a missing author. A module co-authored by Odoo and a partner ("Odoo S.A., Vauxoo") is counted as third party on purpose: an inventory that exists to find third-party code should over-report, not under-report.
- **Third Party** is ticked for everything not published by Odoo S.A., OCA modules included.
- **Non-standard Licence** is ticked for every module whose licence is not LGPL-3 — stronger copyleft (GPL, AGPL), proprietary (OPL-1, OEEL-1, other), or no licence at all. Odoo Enterprise modules are OEEL-1 and appear here by design.
- **Installed But Not Part Of Any App** means: not an application itself, not auto-installed as a link module, and no installed module lists it as a dependency.

## Installation
1. Copy the module into your addons path (or install it from the Apps list).
2. Open Apps, remove the "Apps" filter, search for *Installed Modules Report* and click Install.
3. Only the standard base module is required.

## Configuration
1. No configuration is needed.
2. Access is restricted to the Administration / Settings group. The module grants read access only: no user, administrator included, can write to the report.
3. Optional: add the menu to your favourites for quick access.

## Usage
1. Go to Apps &rarr; Installed Modules Report.
2. The list opens on every installed module, ordered by technical name.
3. Apply a filter (Third Party Only, Non-standard Licence, Installed But Not Part Of Any App, Proprietary Licence, Nothing Depends On It, Pending Upgrade Or Removal) or search by module, author or licence.
4. Group by Origin to see how much of the database is core, Enterprise, OCA or third party.
5. Open a line to read its direct dependencies and the installed modules that require it.
6. Select all and use Export to attach the inventory to your upgrade or audit file.

## Limits, stated plainly
- It reports, it never acts: read access only, no install/upgrade/uninstall, no button that does.
- Only direct dependencies. The lists are one level deep, not transitive, so "nothing depends on it" is not by itself permission to uninstall. For the same reason a module needed only by another loose non-app module is not listed under *Installed But Not Part Of Any App*.
- Declared Dependencies can exceed the Depends On list: the count is what the manifest declares, the list resolves only the dependencies actually installed. They differ when a declared dependency is missing from the database — worth investigating in itself. The reverse direction counts installed modules only, so there count and list always agree.
- Classification is only as good as the manifest. Up to Odoo 18 a module that declares no author at all is recorded by Odoo as "Odoo S.A." and will be reported as core — so an empty *Author Not Declared* filter is not proof that every manifest names its author. Localisation modules that ship with Odoo but declare a community author are reported as third party, because that is what their manifest says. Odoo likewise replaces a missing licence with LGPL-3, so there is no "licence not declared" filter: it could never match.
- The install date is an approximation — the oldest external ID the module created. Modules that create no external ID show an empty date.
- The one-line dependency summaries show the first eight names then "+N more"; the lists on the form are always complete.
- The report is a database view, so it is computed on each search rather than read from a stored table. The install-date lookup probes the external-ID index per module instead of aggregating the whole `ir_model_data` table, so the cost follows the number of installed modules, not the size of your database.

## Support
Email f.ashraf.dev1@gmail.com — questions, bugs and feature requests are all welcome.

License: LGPL-3.
