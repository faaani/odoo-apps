# Password Expiry Policy

Force backend users to change their password every N days — the rotation rule
ISO 27001 and SOC 2 audits ask for, which Odoo does not ship.

Odoo records no password age and has no rotation rule. This module stores the
date of every password change on the user and, once the configured period has
passed, sends the user to a change-password page before letting them back into
the backend.

Free and open source (LGPL-3), Odoo 14.0 through 19.0.

## Safety guards

* **Ships disabled.** Nothing changes until an administrator switches it on.
* **A typo cannot lock out the company.** The period is clamped to a minimum of
  7 days both when it is saved and when it is read. The default is 90 days, the
  ceiling 3650.
* **The administrator is never locked out.** The database superuser (OdooBot,
  uid 1) and the `base.user_admin` account are always exempt, and any other user
  can be flagged exempt on their form.
* **Portal, public and share users are never expired.** Internal backend users
  only.
* **Integrations keep working.** XML-RPC and JSON-RPC authentication and calls,
  `/web/session/*`, assets, images, downloads, scheduled jobs, the mail gateway
  and database initialisation are never intercepted.
* **No redirect loop.** The login page, the logout endpoint, the database
  manager, static assets and the change-password page itself always stay
  reachable.
* **Installing it expires nobody.** Every existing user is stamped with the
  installation date, never with a date in the past.
* **The session survives the change.** After choosing a new password the user
  continues straight into the backend, with no forced re-login.

## Installation

1. Open **Apps**, search for *Password Expiry Policy* and click **Install**.
2. Only the standard `base_setup` and `web` modules are required.
3. Installation stamps every existing user with the current date and time. The
   policy is off until you enable it, so nothing changes yet.

## Configuration

1. Go to **Settings → General Settings** and find the **Users** block.
2. Tick **Password Expiry Policy**.
3. Set **Maximum Password Age (days)** — 90 by default. Anything below 7 is
   raised to 7.
4. Click **Save**.
5. Optional: open **Settings → Users & Companies → Users**, pick an integration
   or break-glass account, open the **Password Expiry** tab and tick **Exempt
   from Password Expiry**.

## Usage

1. Each user's **Password Expiry** tab shows the last password change and the
   resulting expiry date.
2. When the expiry date passes, the user's next backend page load lands on the
   change-password page instead.
3. The user enters their current password and a new one. The clock resets and
   they continue straight into the backend.
4. An administrator can always reset a password the usual way (**Users** form →
   **Change Password**); that resets the clock too.

## What this module deliberately does not do

* It does **not** block API access. XML-RPC and JSON-RPC keep authenticating and
  answering for an expired user, on purpose, so a rotation policy can never take
  your integrations down. The redirect only applies to browser page loads (a GET
  that asks for HTML).
* A backend tab that is **already open** keeps working from its background
  requests until the next page load or refresh.
* It does not enforce password complexity, a password history or a reuse ban —
  only maximum age. It does check that the new password differs from the current
  one and that the confirmation matches.
* It does not send reminder emails before expiry.
* A user with no recorded password change date is never expired: the check fails
  open rather than locking anybody out.

## Support

Email <f.ashraf.dev1@gmail.com> — I read and answer every message.

License: LGPL-3.
