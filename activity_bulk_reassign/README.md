# Reassign Activities in Bulk

When a colleague resigns, changes team or simply goes on holiday, every open activity stays pinned to their name: to-dos, calls, meetings, scheduled follow-ups. Odoo only lets you move them one record at a time. This module adds a **Reassign Activities** wizard: pick the person leaving, pick the person taking over, see how many activities match, and hand them all over at once.

- One action moves every open activity of a user to a colleague.
- Filter the hand-over by activity type and by due-date range.
- The wizard previews how many activities match before anything is moved.
- A note is logged in the chatter of every affected document.
- Completed and cancelled activities are never touched.
- Only the activities the current user is allowed to modify are reassigned; no access rule is bypassed.
- An archived user can still be chosen as the source, which is exactly when a hand-over is needed.

## Installation
1. Copy the module folder into your Odoo add-ons path.
2. Open Apps, click Update Apps List, then search for Reassign Activities in Bulk.
3. Click Install. Only the standard mail module is required.

## Configuration
1. Nothing to configure — the wizard is ready as soon as the module is installed.
2. The menu is available to every internal user, under Discuss &rarr; Reassign Activities.
3. Access is enforced by Odoo itself: a user only ever moves the activities they are allowed to modify, so no extra rights have to be granted.

## Usage
1. Open Discuss &rarr; Reassign Activities.
2. In From User, choose the person whose activities have to be handed over; in To User, choose the person taking them.
3. Optionally restrict the move with Activity Types (leave empty for all types) and with the Due From / Due To range.
4. The banner at the top of the wizard shows how many open activities currently match; it updates as you change the filters.
5. Leave Log a Note ticked to keep a trace in the chatter of every affected document, then click Reassign.
6. A confirmation tells you exactly how many activities were moved. Each one now appears in the new assignee's to-do list.

## Notes
- Someone who already left the company is usually archived; archived users stay selectable as the source, so their backlog can still be handed over.
- From 17.0 on, Odoo keeps completed activities as archived records; the wizard skips them, exactly as it skips the ones older series delete.
- Up to Odoo 16.0, Odoo itself refuses to assign an activity to someone who cannot open the related document, and it refuses the whole batch. The wizard reports that refusal instead of moving part of the selection; from 17.0 on, Odoo dropped that check.

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
