# -*- coding: utf-8 -*-
# Part of cron_watchdog_alert. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        # Piggyback on backend page loads: if the whole cron worker is dead,
        # no cron (including the watchdog) runs — but people still use Odoo.
        # The tick throttles itself and can never raise.
        result = super(IrHttp, self).session_info()
        self.env['ir.cron']._watchdog_web_tick()
        return result
