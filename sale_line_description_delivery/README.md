# Sale Line Description on Delivery

The description you type on a sale order line never reaches the warehouse:
transfers and delivery slips only show the product's own description. This
module carries the sale order line description onto the stock moves, so
pickers and customers see engraving texts, packing notes and customer
references exactly as sold. Free, LGPL-3, Odoo 14.0 – 19.0.

## Installation
1. Install from **Apps** (search "Sale Line Description on Delivery").
2. Depends only on standard `sale_stock`.

## Configuration
None needed — active for every sale order confirmed after installation.
Optional kill switch for technical users: create the System Parameter
`sale_line_description_delivery.enabled` = `False` (Settings → Technical →
System Parameters) to restore standard behavior without uninstalling.
Truthy values (`True`/`1`/`yes`) re-enable it.

## Usage
1. On a sale order line, write your text under the product name in the
   line description (engraving text, packing instructions, references).
2. Confirm the order. The generated transfer's moves carry that text in
   their picking description — without duplicating the product name, and
   correctly matched in multi-language databases.
3. Print the **Delivery Slip**: the text appears under the product, exactly
   as typed. Lines whose description is just the product name keep Odoo's
   standard behavior.

## Notes per version
Identical behavior on all supported series (14.0 – 19.0). Internally, 19.0
uses the new computed picking-description mechanism; earlier series use the
procurement-values hook.
