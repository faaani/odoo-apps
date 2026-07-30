# Global Default Saved Filter

Odoo's favorites menu makes **Use by default** and **Share with all users**
mutually exclusive, so the usual advice is to duplicate the same filter for
every single user. This module adds a **Default for All Users** flag on shared
filters instead. Free, LGPL-3, Odoo 14.0 – 19.0.

## Installation
1. Install from **Apps** (search "Global Default Saved Filter").
2. Standard `base` and `web` only.

## Configuration
None. The flag appears on shared filters right after installation.

## Usage
1. Save a filter as usual with **Share with all users** ticked (favorites menu).
2. Enable developer mode and open **Settings → Technical → User-defined Filters**
   (or Actions → Filters), pick your shared filter and tick
   **Default for All Users**. The flag is hidden on personal filters.
3. Every user who has not set a personal default now opens that view with the
   filter already applied. A user's own default always wins over the global one.
4. Untick the flag to go back to standard behavior; nothing is left behind.

## Notes
- Only one global default applies per model: if several are flagged, the oldest
  one wins, deterministically.
- An existing shared filter that a technical user already marked default in the
  database keeps working — this module never overrides it.
- 19.0 stores filter sharing in `user_ids` (many2many) instead of `user_id`;
  the module handles both automatically.
