# Private Address Type for Contacts

Keep personal addresses out of sight: a dedicated **Private Address** type on
contacts plus a security group that decides exactly who may see them.

Odoo 17 removed the Private Address type that existed through 16.0, so
sensitive personal addresses (a director's home, an employee's flat, a VIP
customer's residence) became ordinary contacts every internal user can browse.
This module restores the type on Odoo 17/18/19 and, on **every** version
14.0-19.0, adds a clear access separation that core never made visible.

## Features

- **Private Address type restored** on Odoo 17.0, 18.0 and 19.0
  (on 14.0-16.0 the type already exists in core).
- **Security group "See Private Addresses"**: internal users outside the group
  cannot read, write or delete private addresses - they never appear in lists,
  searches, exports or name lookups on `res.partner`.
- **Administrators keep full visibility** (the Settings group is implied).
- **Group-gated search filter** "Private Addresses" in the contact search view.
- **Login-safety constraint**: a partner linked to an active user can never be
  set to Private Address, and a user can never be pointed at a private partner.
- **Safe uninstall** on 17.0+: an uninstall hook converts remaining private
  addresses to "Other Address" before the selection value disappears (rows the
  hook cannot reach fall back to "Contact" at field level).
- **Safe install on upgraded databases** (17.0+): a post-install hook resets
  user-linked partners that still carry `type='private'` from an earlier
  version to "Other Address", so nobody's login record silently disappears.
- Normal contacts, companies, portal and public users are unaffected; new
  partners still default to type "Contact".

## Installation

1. Copy the `partner_private_address_type` folder into your addons directory.
2. Restart the Odoo server.
3. Activate developer mode, open **Apps** and click **Update Apps List**.
4. Search for "Private Address Type for Contacts" and install it.
   Only `base` is required.

## Configuration

1. On Odoo 14.0-18.0, activate developer mode (like all Extra Rights groups,
   the checkbox is only rendered on the user form in developer mode). On
   Odoo 19.0 it is visible without developer mode.
2. Open **Settings > Users & Companies > Users** and pick a user.
3. In the **Extra Rights** section, tick **See Private Addresses** and save.
4. Administrators are members automatically.

## Usage

1. On a contact, open **Contacts & Addresses**, click **Add** and pick the
   **Private Address** type for the sensitive address.
2. Users outside the group never see that record; members can use the
   **Private Addresses** search filter to review them all.
3. Marking a user's own contact as private is refused with a clear message.

## Version notes

- **14.0-16.0**: core has the type and a *hidden* technical group. This module
  makes the separation explicit: a clearly named group (which also grants the
  core "Access to Private Addresses" group so core/HR/accounting rules stay
  consistent), its own record rules, the filter and the constraints. On these
  versions the module also makes Settings administrators members of the group
  automatically - core does not do that by default, so admins gain visibility
  of existing private addresses (including HR home addresses) at install time.
  Uninstalling revokes the core-group access the module granted: users who
  only held "Access to Private Addresses" through this module lose it again,
  while administrators and users who hold it through other apps (e.g. HR)
  keep it.
- **17.0-19.0**: core removed the type; the module restores it and adds the
  separation. Uninstalling converts remaining private addresses to "Other".

## Limitations

- Record rules filter ORM access to `res.partner`. Raw-SQL reports or
  integrations bypass record rules by design.
- Portal and public users are governed by Odoo's own rule: they can only read
  partners inside their own commercial family. Within that family this module
  does not additionally hide a private address from them (same as core 14-16).
- The module controls access; it does not encrypt or mask address data.

## Support

Questions or issues: f.ashraf.dev1@gmail.com

License: LGPL-3. Author: Farhan Ashraf.
