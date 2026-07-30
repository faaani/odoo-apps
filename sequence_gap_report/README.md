# Sequence Gap Report

Odoo sequences leave holes: a deleted draft, a discarded order, a cancelled entry, and the numbering jumps. Auditors and tax authorities ask about every one of them, and Odoo offers no way to find them. This module adds a read-only wizard that scans any numbered field of any model and lists every missing number, series by series, with the documents that sit just before and just after the hole.

- Works on any model: `account.move`, `sale.order`, `purchase.order`, `stock.picking`, or anything else. Depends on `base` only.
- Understands any format: each value is split into a prefix and its trailing digits, so series never mix.
- Shows the document before and after every gap, and preserves zero padding in the missing numbers.
- One single read of one column (up to 200,000 numbered documents per scan), a cap on the number of reported gaps, and a clear message when the report is truncated.
- Honest about its limits: only documents you are allowed to read are counted, and the summary says so, because numbers hidden by access rights look like gaps.
- Strictly read-only: nothing is created, modified or renumbered.

## Installation
1. Copy the `sequence_gap_report` folder into your addons directory.
2. Open Apps, click Update Apps List and search for Sequence Gap Report.
3. Click Install. Only the standard `base` module is required.

## Configuration
1. None. The report is available under Settings &rarr; Sequence Gap Report.
2. The wizard opens on `account.move` / `name`; type any other model and field if you scan something else.
3. Maximum Gaps (default 500) caps how many gaps are listed; the report says so when there are more.

## Usage
1. Go to Settings &rarr; Sequence Gap Report.
2. Enter the model to scan and the field holding the number, usually `name`.
3. Keep Include Archived ticked: archived documents still consumed their number.
4. Click Scan for Gaps. Each line shows the first and last missing number, how many numbers the hole covers, and the documents immediately before and after it.
5. Click Open Full List to sort, group or export the result; click New Scan to check another model.

## Notes
Identical behavior on every supported series (14.0 – 19.0).

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
