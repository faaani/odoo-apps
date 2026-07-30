# -*- coding: utf-8 -*-
# Part of failed_mail_alert. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

from .mail_mail import (
    DEFAULT_AGE_MINUTES,
    DEFAULT_THRESHOLD,
    MIN_AGE_MINUTES,
    MIN_THRESHOLD,
    PARAM_AGE_MINUTES,
    PARAM_ENABLED,
    PARAM_THRESHOLD,
    int_param,
)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # None of these three is bound with config_parameter= on purpose:
    # ir.config_parameter.get_param() returns the DEFAULT for any falsy stored
    # value, so a default-True switch could never be turned off and a 0 would
    # always read back as the default. They are stored as explicit strings
    # through get_values()/set_values() instead.
    failed_mail_alert_enabled = fields.Boolean(
        string='Failed Email Alerts',
        help='Email Settings administrators when outgoing messages pile up in '
             'the queue instead of being delivered.',
    )
    failed_mail_alert_threshold = fields.Integer(
        string='Alert Above (emails)',
        help='Alert once at least this many messages are stuck in the outgoing '
             'queue. Values below %s are treated as %s.' % (MIN_THRESHOLD, MIN_THRESHOLD),
    )
    failed_mail_alert_age_minutes = fields.Integer(
        string='Minimum Age (minutes)',
        help='Messages queued more recently than this are still considered '
             'normal traffic and are not counted. Values below %s are treated '
             'as %s.' % (MIN_AGE_MINUTES, MIN_AGE_MINUTES),
    )

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        icp = self.env['ir.config_parameter'].sudo()
        res.update(
            failed_mail_alert_enabled=icp.get_param(PARAM_ENABLED, 'True') == 'True',
            failed_mail_alert_threshold=int_param(
                icp.get_param(PARAM_THRESHOLD, DEFAULT_THRESHOLD), DEFAULT_THRESHOLD),
            failed_mail_alert_age_minutes=int_param(
                icp.get_param(PARAM_AGE_MINUTES, DEFAULT_AGE_MINUTES), DEFAULT_AGE_MINUTES),
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PARAM_ENABLED, str(bool(self.failed_mail_alert_enabled)))
        icp.set_param(PARAM_THRESHOLD, str(max(self.failed_mail_alert_threshold or 0, 0)))
        icp.set_param(PARAM_AGE_MINUTES, str(max(self.failed_mail_alert_age_minutes or 0, 0)))
