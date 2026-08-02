# Login Attempt Throttling and Account Lockout

Stop password guessing on the Odoo login screen. Every attempt is recorded, repeat
failures are locked out for a few minutes, and nobody can be locked out for good.

Supported: Odoo 14.0, 15.0, 16.0, 17.0, 18.0 and 19.0. Licence: LGPL-3.

## Why

Out of the box Odoo accepts an unlimited number of wrong passwords on the login
screen. Somebody who knows one of your users' e-mail addresses can run a dictionary
against it all night: nothing slows them down, nothing is written down, and nobody is
told. Odoo's own built-in cooldown counts per IP address, lives in memory only and is
not shared between workers, so it is lost on every restart.

## What it does

* Records every login attempt: the login used, the source IP address, and the outcome
  (successful, failed, or blocked while locked out).
* After a configurable number of failures for the same login (5 by default), refuses
  that login for a configurable number of minutes (15 by default), even if the correct
  password is supplied.
* Every lockout expires by itself. There is no permanent lock, and continuing to knock at
  a locked login does not extend the lockout already running. An attacker who keeps trying
  can still trigger a fresh lockout each time one lapses, which is why any administrator
  can release a lockout instantly.
* A successful login clears the counter.
* Unknown logins are throttled identically, so the login form cannot be used to tell
  real accounts from invented ones.
* Upper case and lower case share one counter.
* Optional e-mail alert to every Settings administrator when a lockout starts.
* Administrators can release a lockout in one click.
* A scheduled action purges attempts older than the retention period (30 days by
  default).

## Installation

1. Copy the `auth_login_lockout` folder into your Odoo add-ons directory.
2. Restart the Odoo service.
3. Log in as an administrator and go to **Apps**.
4. Click **Update Apps List** (you may need to switch on developer mode first).
5. Search for **Login Attempt Throttling and Account Lockout** and press **Install**.

Protection is active immediately, using the default policy.

## Configuration

Go to **Settings > General Settings** and scroll to the **Login Security** block.

| Setting | Default | Meaning |
|---|---|---|
| Lock Out Repeated Failed Logins | On | Turns the feature on or off. Off stops both the lockouts and the recording. |
| Failed Attempts Allowed | 5 | Failures for the same login tolerated before it is locked. |
| Lockout Duration (minutes) | 15 | How long the login stays refused. |
| Keep Attempts For (days) | 30 | How long recorded attempts are kept before the purge deletes them. |
| E-mail Administrators On Lockout | Off | Mails every Settings user as soon as a lockout starts. |

Press **Save**. Changes apply to the next login attempt; no restart is needed.

## Usage

1. There is nothing to do day to day: the module counts failures and locks logins out
   on its own.
2. To review activity, open **Settings > Users and Companies > Login Attempts**. The
   list is visible to Settings administrators only.
3. Narrow it with the built-in filters: Failed, Blocked By Lockout, Successful, Still
   Counting, Released, Today, Last 7 Days. Group by login, result, IP address or date.
4. A locked-out user sees the ordinary "wrong login or password" message. That is
   deliberate: revealing the lockout, or how long it lasts, would hand an attacker your
   policy. The real reason is written to the server log.
5. To let a colleague back in immediately, filter on **Still Counting**, select their
   failed rows and choose **Release lockout** from the **Actions** menu. The rows stay
   in the list, flagged as released, and stop counting.
6. Otherwise the lockout lifts on its own once the configured minutes have passed.

## What this module does not do

* It guards the login endpoint (the web login form and the `authenticate` call used by
  XML-RPC and JSON-RPC clients). It is not a network-level rate limiter: put a reverse
  proxy in front of Odoo to absorb volumetric attacks.
* Re-validating an already known user id is not throttled, because reaching that path
  requires knowing a valid user id in the first place.
* The lockout is per login, not per IP address. Locking per IP would punish everybody
  behind a shared office connection and would be easy to evade from a botnet. The
  trade-off is that an attacker can get a real user temporarily locked out, which is
  why blocked attempts never extend a lockout and why any administrator can release one.
* An attacker can keep a login locked out by triggering a new lockout each time the
  previous one lapses. Nothing can prevent that while the policy is keyed on the login
  rather than the source address. Practical answers: release the lockout from the attempt
  list, block the source at your reverse proxy, or switch the policy off while you deal
  with it.
* The log stores what was typed in the login box, verbatim. If somebody types their
  password into the login field by mistake it will appear in the attempt list, so treat the
  log as sensitive. It is restricted to Settings administrators and the retention period
  bounds how long it is kept. Odoo's own server log already records the login of every
  failed attempt in the same way.
* The alert only fires for logins that match a real, active user account. Lockouts still
  apply to invented logins; they just do not generate mail.
* It does not add two-factor authentication, password strength rules or CAPTCHA.
* The optional alert uses Odoo's outgoing mail queue, so an outgoing mail server must be
  configured for it to be delivered.

## Support

Questions, bug reports and suggestions: **f.ashraf.dev1@gmail.com** (please mention your
Odoo version).

Published by Farhan Ashraf. Licensed under LGPL-3.
