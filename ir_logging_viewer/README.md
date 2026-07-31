# Server Log Viewer

Read the log entries Odoo stores in the database — filter by level, logger, date
and message text, with a retention cleanup — without opening an SSH session.

Free and open source (LGPL-3). Supported on Odoo 14.0, 15.0, 16.0, 17.0, 18.0 and 19.0.

## Read this first — what this module can and cannot show

This module shows only what Odoo **persists to the database**, in the `ir_logging`
table. Odoo writes there when the server runs with the `log_db` option
(`--log-db=<database>` on the command line, or `log_db = <database>` in
`odoo.conf`), plus the entries written by "Execute Python Code" server actions
that call `log()`.

It is **not** a viewer for the server log *file* (`--logfile`), it cannot show
anything logged before `log_db` was switched on, and on hosting where you cannot
change server options the table may simply stay empty. The module never writes
log entries itself.

## What it adds

- **Filter by level** — one-click Errors, Warnings, Info and Debug filters, matching
  both the uppercase level names the server writes and the lowercase ones a Python
  server action writes.
- **Filter by logger** — search part of a logger name (`odoo.sql_db`,
  `odoo.addons.mail`…) or of the function name.
- **Filter by date** — Today, Last 7 Days, Last 30 Days, plus the standard
  month / quarter / year date picker.
- **Free-text search inside the message** — find an exception class, a table name or
  a reference anywhere in the message body or traceback.
- **Group by level or logger** (also by type and database).
- **Short in the list, complete in the form** — the list shows a shortened first line;
  the form shows the entire message and traceback. Nothing is truncated in storage.
- **Colour-coded rows** — errors red, warnings orange, debug greyed out.
- **Retention window and daily cleanup** so the table cannot grow without bound.
- **Confirmed clear wizard** that announces how many entries it will delete.
- **Administrator only** — menus, viewer and wizard are restricted to
  `base.group_system`.

## Installation

1. Copy the module into your addons path, or install it from the Apps list.
2. Open **Apps**, remove the "Apps" filter, search for *Server Log Viewer* and click
   **Install**.
3. Only the standard `base_setup` module is required — no other dependency.

## Configuration

1. **Make Odoo store logs in the database.** Add `log_db = <your database name>` to
   `odoo.conf` (or start the server with `--log-db=<database>`) and restart. Without
   this the table stays empty and the screen has nothing to show — that is an Odoo
   server option, not something a module can switch on.
2. Optionally add `log_db_level = warning` (or `error`) so only the important records
   are stored; the Odoo default is `warning`.
3. Go to **Settings → General Settings → Server Logs**, tick **Delete Old Log
   Entries** and set **Retention (days)** — 30 is a sensible start. Leave it unticked
   and nothing is ever deleted.
4. The scheduled action *Server Log Viewer: apply log retention* runs once a day. It is
   installed active, but does nothing while the retention setting is off.
5. Access is restricted to the **Settings** administration group; no other user can
   open the screen or clear entries.

## Usage

1. Go to **Settings → Server Logs → Log Entries**. The list opens on the last 7 days,
   newest first.
2. Click *Errors* to see only errors and criticals, or *Warnings*, *Info*, *Debug*.
   Combine with *Today*, *Last 7 Days* or *Last 30 Days*.
3. Type in the search box: the first suggestion searches the **message** text, the
   second searches the **logger** and function name.
4. Use **Group By → Level** or **Logger** to see where the noise comes from, then open
   a group.
5. Click a row to open it: the form shows the whole message and traceback, plus the
   file, function and line.
6. To trim the table by hand, go to **Settings → Server Logs → Clear Log Entries**,
   choose "older than N days" or "every entry", check the count, tick the confirmation
   and confirm.

## Notes and limitations

- Odoo already ships a minimal Logging list under *Settings → Technical → Database
  Structure* (developer mode). This module does not replace or modify it — it adds its
  own screen and leaves that one exactly as it was.
- Grouping by **Level** groups on the raw value stored by the server. A Python server
  action calling `log(message, level='info')` stores a lowercase value, so it forms its
  own group; the shipped level *filters* match both spellings.
- Free-text search on the message body scans the message column; on a very large log
  table that is slower than the level or date filters.
- Deleting log entries is permanent. Nothing else is touched: no other record, no
  setting, no attachment, and never the server log file.
- Identical behaviour on every supported series (14.0 – 19.0).

## Support

Email <f.ashraf.dev1@gmail.com> — questions, bugs and feature requests are welcome.

## License

LGPL-3.
