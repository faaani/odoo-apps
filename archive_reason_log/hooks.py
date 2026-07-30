# -*- coding: utf-8 -*-
# Part of archive_reason_log. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
"""Install-time hook.

The "Archive with Reason" entry has to be attached to one model at a time
(``binding_model_id`` is a Many2one), so a binding action is generated for every
installed model that can actually be archived. Re-run it from
Settings > Archived Records > Update Action Menus after installing new apps.
"""


def post_init_hook(env):
    env['archive.reason.wizard']._sync_action_bindings()
