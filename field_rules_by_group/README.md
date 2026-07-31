# Field Rules by Group

Make any field read-only, invisible or required per user group - no Studio, no
custom code.

Every Odoo project hits the same requests: "this field must be read-only for
regular users", "tidy this form for that team", "make the reference mandatory
for accounting". Out of the box that means editing XML views or paying for
Studio. This module adds a simple rule table instead: pick a model, pick a
field, pick the user groups, tick the restriction. Done.

## Features

- **Read-only, invisible or required** - per field, per user group.
- **Server-enforced read-only** - read-only rules are also enforced
  server-side on create and write, so a restricted user's direct API writes
  are refused as well.
- **Works on any model** - standard or custom, including models added by other
  apps.
- **Empty groups = everyone** - leave the group list empty to apply a rule to
  all users.
- **Administrators stay safe** - rules never apply to system administrators
  unless a rule explicitly opts in, so an admin can always repair data.
- **Zero setup cost** - depends on `base` only; uninstall and every form is
  back to normal.

## Installation

1. Install the module from the Apps menu.
2. No other module is required; it only depends on `base`.

## Configuration

1. Enable developer mode (Settings > General Settings > Developer Tools).
2. Open **Settings > Technical > Field Rules**.
3. Create a rule: choose the model, the field and the user groups, then tick
   Read-Only, Invisible or Required.
4. Leave User Groups empty to apply the rule to every user.
5. Tick "Apply to System Administrators" only if the rule must cover admins.

## Usage

1. A user in one of the rule's groups opens the form: the field shows up
   read-only, hidden or required, exactly as configured.
2. If a restricted user tries to write a read-only field through the API,
   the server refuses with a clear message naming the field and the rule.
3. Archive a rule to suspend it, delete it to remove it - the change applies
   immediately.

## Honest limitations

- Rules apply to **form views only** - list, kanban and other views are not
  stamped (a read-only rule still blocks list-view edits server-side).
- **Invisible hides the field on form views only**; the value remains
  readable via API calls, exports, list/kanban views and embedded subviews.
  It is a UI convenience, not an access control.
- **Read-only is not enforced on system/sudo flows**: writes performed by
  Odoo itself or through sudo (for example a user editing their own
  preferences) are not blocked.
- **Required is enforced by the form only**, not server-side, in this version.
- System administrators are exempt by default - on purpose, so they can always
  fix data. Each rule can opt in to cover them.
- No conditional rules (e.g. "only when state is draft") in this version.

## Support

Questions or suggestions: f.ashraf.dev1@gmail.com

License: LGPL-3
