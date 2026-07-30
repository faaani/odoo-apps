# Database Size Report

When an Odoo database starts filling the disk, nothing in the interface says what is responsible — answering it means opening `psql` and knowing the right catalog query. This module adds a read-only report for administrators: the size of the database on disk at the top, then every table with its size, its index size, the total it really costs, an estimated row count and the Odoo model stored in it, sorted biggest first.

The figures come from the PostgreSQL catalog through fixed queries that take no user input at all. None of your tables is scanned, no row is counted one by one, and not a single business record is read, changed or deleted.

## Installation
1. Copy the `database_size_report` folder into your addons path (or install it from the Apps store).
2. Open Apps, click Update Apps List, search for Database Size Report and click Install.
3. No external Python library and no other module is required — it only depends on `base`.

## Configuration
1. There is nothing to configure. The report reads the database you are connected to.
2. Access is limited to the Settings group (Administration: Settings). Give that group to anyone who should be able to run the report — the sizes cover the whole database, including tables the user has no access to.

## Usage
1. Go to Settings &rarr; Database Size &rarr; Size Report. The report opens already measured.
2. Read the top of the form: the database size on disk, when it was measured, how many tables it holds and what they total.
3. Read the list underneath: the biggest tables first, each with its Odoo model, estimated rows, table size, index size, total size and share of the total.
4. The **Note** column explains the tables that are usually responsible for a growing database: `mail_message` and `mail_tracking_value` (chatter messages and their tracked changes), `mail_notification` and `mail_followers`, `ir_attachment`, `ir_logging` and the `*_log` tables.
5. Change **Tables to List** (1 to 2000) and press **Refresh** to list more (or fewer) tables. The totals always cover every table.
6. Press **Open As List** to see the same tables in a normal list view, where you can filter (with/without an Odoo model, over 10 MB, over 100 MB), group them, and export them if your user has export rights.

## What the figures mean
* **Table Size** — the table itself, including its TOAST overflow storage (`pg_table_size`).
* **Index Size** — all of the table's indexes (`pg_indexes_size`).
* **Total Size** — the sum of both (`pg_total_relation_size`): what the table really costs on disk.
* **Rows (estimate)** — PostgreSQL's own estimate (`reltuples`), maintained by ANALYZE and autovacuum. It is **not** an exact count; that is deliberate, because `COUNT(*)` on every table would read the whole database. A table PostgreSQL has never analysed shows 0 and is flagged *No Statistics* (PostgreSQL 14 and above; older versions cannot tell an unanalysed table from an empty one).
* **Database on Disk** — `pg_database_size`, which is larger than the total of the tables because it also holds the PostgreSQL catalogs and the free space left behind by deleted rows.

## Notes and limitations
The report is strictly read-only where your data is concerned: it never reads, changes or deletes a business record, and it never offers to delete anything. The only thing it writes is the report you are looking at, a temporary record Odoo cleans up on its own.

Tables that belong to no Odoo model (the relation tables behind many2many fields, tables left by uninstalled modules, non-Odoo tables in the same database) are listed with an empty model — they are exactly the rows worth knowing about.

Only real tables, partitioned tables and materialized views are listed; SQL views have no storage of their own, so they cannot appear. Sizes are read from the PostgreSQL catalog and reflect what is on disk, which is normally larger than the live data, because deleted rows keep their space until VACUUM reuses it.

Identical behavior on every supported series (14.0 – 19.0).

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
