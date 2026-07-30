# Manage Followers in Bulk

Odoo adds or removes a follower one record at a time. Putting the new account manager on ninety customers, or taking a departed colleague off every open project, means opening ninety chatters. This module adds a **Manage Followers** action: select the records, pick who to add and who to remove, and the change is applied to the whole selection at once.

- Add and remove in a single pass, applied to every selected record.
- Optionally choose the message subtypes for the followers being added.
- Records that are already followed are never duplicated.
- Runs as the current user — records they may not write are refused, never silently changed.
- A notification reports exactly how many follower entries were added and removed.

## Installation
1. Copy the `followers_bulk_manage` folder into your addons path.
2. Open Apps, click Update Apps List, search for Manage Followers in Bulk.
3. Click Install. Only the standard mail module is required.

## Configuration
1. Nothing to configure — the action is available on Contacts immediately after installation.
2. To offer it on another model, open Settings > Technical > Actions > Window Actions, find Manage Followers and add that model to its bindings.
3. Access is granted to every internal user (Employee); each user can still only change records they are allowed to write.

## Usage
1. Open a list view and tick the records you want to update.
2. Choose Actions > Manage Followers in the toolbar.
3. Fill Followers to Add, Followers to Remove, or both. A partner cannot appear in both lists.
4. Optionally select the message subtypes the new followers should be subscribed to; leave it empty to use the model defaults.
5. Click Apply. A notification reports how many follower entries were added and removed.

## Notes
Identical behavior on every supported series (14.0 – 19.0). The subscription calls use keyword arguments so the 14.0 `message_subscribe(partner_ids, channel_ids, subtype_ids)` signature can never re-bind subtypes to channels.

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
