# Record Rule Tester

"Why can't this user see that order?" is normally answered by opening Settings → Technical → Record Rules, reading a few domains full of `user.company_id`, and guessing.

This module answers it by asking the server. Pick a user, pick a model, press **Run Test**: the wizard runs the searches **as that user**, so every number comes out of Odoo's own rule engine rather than a re-implementation of it. Give it a record id as well and it tells you whether that user can read that exact record — and when they cannot, which rules exclude it, taken from `ir.rule._get_failing()`, the routine Odoo itself uses to name rules in its error messages.

## What you get
- **Applicable record rules** — global ones and group ones listed separately, with the operations each covers, the tested user's groups the rule comes through, and its domain. Global rules are ANDed with everything else; group rules are ORed with each other, and the screen says so.
- **Per operation** — for read, write, create and delete: whether an access control line grants it on the model at all, how many record rules apply, and how many records the user can actually reach.
- **A verdict on one record** — "can read" or "cannot read", with the blocking rules named and flagged in red. A record that does not exist is reported as missing, not blamed on a rule.
- **A comparison figure** — the same count taken for you, the administrator running the test.
- **Multi-company aware** — the evaluation uses every company the *tested* user may access, never your own company switcher, and names the companies it used.
- **No access is a result, not a crash** — a model the user has no access control line for is reported plainly instead of raising.

## Installation
1. Copy the `record_rule_tester` folder into your addons path (or install it from the Apps store).
2. Open Apps, click Update Apps List, search for Record Rule Tester and click Install.
3. No external Python library and no other module is required — it only depends on `base`.

## Configuration
1. There is nothing to configure. The tester works on the users, models and record rules already in your database.
2. Access is limited to the Settings group (Administration: Settings). Give that group to anyone who should be able to run a test — nobody else can open the screen or read its results.
3. The tested user needs no preparation of any kind: they are never logged in, never written to, and never notified.
4. To see technical model names next to the human ones (`res.partner` rather than Contact), switch on the developer mode — the tester shows both either way.

## Usage
1. Go to Settings → Users & Companies → Record Rule Tester.
2. Pick the User whose access you are investigating and the Model to test, for example Contact (`res.partner`).
3. Optionally fill in a Record ID — the database id of the one record somebody says they cannot see. Leave it at 0 to test the model only.
4. Optionally lower or raise the Count Cap (default 10 000, maximum 200 000) to control how far the counts may walk on a very large table.
5. Press Run Test.
6. Read the Result block: model access, how many records the user can read, how many you can read for comparison, whether a count was capped, how many global and group rules apply, and the companies the evaluation used.
7. Read the Verdict On The Record: "can read", "cannot read" with the rules that exclude it named, "no such record", or "no access to this model".
8. Open the Operations tab for the read / write / create / delete breakdown, and the Applicable Record Rules tab for the rules themselves — the ones keeping your record out of reach are flagged and shown in red.
9. Check the Notes tab: it states the caveats that apply to that particular run (superuser, archived records, the cap, models that delegate through `_inherits`).
10. Change the rule in Settings → Technical → Record Rules, press Run Test again, and watch the numbers move.

## Read-only, and it never widens access
The tester only ever runs searches. It never creates, edits or deletes a record rule or an access control line, and it never calls `sudo()` around an access decision — the evaluation environment is built with superuser mode explicitly off, so what you are shown is what Odoo would really do to that user. It never displays the content of a record either: you get counts, rule names, rule domains and a yes/no verdict, never field values.

Both the wizard and its two result models are restricted to Settings administrators (`base.group_system`) in `ir.model.access.csv`, and the Run Test method re-checks that group before it does anything. Every evaluation runs inside a savepoint, so a record rule with a broken domain is reported as a message on the screen instead of leaving the cursor unusable.

## Limitations
**Domains are shown exactly as stored.** `user.company_id` and friends are not expanded into values. What the user really ends up seeing is the evaluated result — the counts and the verdict — which is produced by really running the searches.

**Counts stop at a cap** (10 000 by default, adjustable from 1 up to 200 000). A count that reached the cap is flagged as capped, so it reads as "this many or more", never as an exact total.

**The Write and Delete counts are records the user can both see and write/delete**: a search always applies the read rules on top of the operation's own rules. **Create has no count at all** — create rules validate the values of a new record, they do not filter existing ones — and the screen says so instead of showing a meaningless zero.

**Rules inherited through `_inherits`** (say `product.product` reaching `product.template`) are applied by the server but are not listed here; a note tells you to run the test again on the parent model.

**Field-level access** (`groups=` on a field), menu visibility and button-level checks are out of scope. This is about record rules and model access.

Counts are taken with archived records included and with every company the tested user may access enabled. Abstract models are refused with a clear message, because they hold no records.

**Testing the superuser** reports what an ordinary user with the same groups would see; in real operation the superuser bypasses rules entirely, and a note on the screen says so.

The "no such record" answer comes from a plain lookup on the table, so the tester can tell an administrator that a record id exists even when their own record rules hide it. It never shows that record's content, and this is one of the reasons the whole tool is limited to Settings administrators.

## Version notes
Identical features on every supported series (14.0 – 19.0). The module adapts to the API each series ships: `check_access_rights()` on 14.0 – 17.0 and `has_access()` on 18.0 / 19.0 for model access, and the user's group set read from `groups_id` on 14.0 – 18.0 or `all_group_ids` on 19.0, so implied groups are always taken into account.

Free, LGPL-3, Odoo 14.0 – 19.0.

## Support

Questions, bugs or feature requests: f.ashraf.dev1@gmail.com
