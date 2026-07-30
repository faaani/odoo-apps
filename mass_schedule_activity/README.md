# Schedule Activities in Bulk

Odoo schedules activities one record at a time. Assigning a follow-up call to forty customers, or a review task on every overdue invoice, means opening forty records. This module adds a **Schedule Activity** action: select the records, fill the activity once, and it is created on all of them.

## Installation
1. Open Apps, search for Schedule Activities in Bulk and click Install.
2. Only the standard mail module is required.

## Configuration
1. None. The action is available immediately on Contacts; a technical user can bind it to other models via Settings &rarr; Technical &rarr; Actions &rarr; Server Actions bindings.

## Usage
1. Open a list view, tick the records you want.
2. Choose Actions &rarr; Schedule Activity in the toolbar.
3. Pick the activity type, assignee and due date, add a summary, then click Schedule.
4. Each selected record now carries the activity, visible in its chatter and in the assignee's To-Do list.

## Notes
Identical behavior on every supported series (14.0 – 19.0).

Free, LGPL-3, Odoo 14.0 – 19.0.
