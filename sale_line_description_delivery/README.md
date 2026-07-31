# Sale Line Description on Delivery

What you typed on the order is what the warehouse sees.

Engraving texts, packing notes, customer references — you write them on the sale order line, and then the transfer and the delivery slip show only the product description. Core Odoo closed this as "wishlist"; the existing solutions are paid. This module carries the sale line description onto the stock moves the moment the order is confirmed.

* **Zero configuration** — install it and every newly confirmed order does the right thing.
* **No duplicated product names** — only the extra text you typed is added; language-aware matching for multi-language databases.
* **Standard behavior preserved** — lines whose description is just the product name are left untouched.
* **Prints on the delivery slip** — uses Odoo's own picking-description field, so every report that shows it benefits.

## Installation
1. Open Apps, remove the default "Apps" filter if needed, and search for Sale Line Description on Delivery.
2. Click Install. Only the standard `sale_stock` module is required.

## Configuration
1. None — the module is active for every sale order confirmed after installation.
2. Optional kill switch (technical): set the System Parameter `sale_line_description_delivery.enabled` to `False` (Settings &rarr; Technical &rarr; System Parameters) to restore standard behavior without uninstalling.

## Usage
1. On a sale order line, write your text under the product name in the description — engraving text, packing instructions, references.
2. Confirm the order: the transfer's moves now carry that text as their picking description.
3. Print the Delivery Slip — the text appears under the product, exactly as typed.

## Notes
Only orders confirmed **after** installation are affected; the module does not rewrite transfers that already exist. Lines whose description is nothing more than the product name are deliberately left alone, so nothing is duplicated on the slip.

Identical behavior on every supported series (14.0 – 19.0). Internally, 19.0 uses the new computed picking-description mechanism; earlier series use the procurement-values hook.

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
