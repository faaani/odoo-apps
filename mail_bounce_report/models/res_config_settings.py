# -*- coding: utf-8 -*-
# Part of mail_bounce_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import fields, models

from .mail_bounce_report import MAX_THRESHOLD, PARAM_THRESHOLD


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Explicit get/set instead of config_parameter=: get_param() hands back the
    # default for any falsy stored value and set_param() DELETES the parameter
    # when given a falsy one, so a deliberately configured threshold of 0 could
    # never be stored nor read back through the shorthand.
    mail_bounce_report_threshold = fields.Integer(
        string='Bounce Threshold',
        help='A contact is flagged "Above Threshold" once its bounce counter '
             'reaches this number (the test is >=, i.e. inclusive). The default '
             'of 10 is the same limit Odoo\'s own mail code uses before it '
             'considers an address dead. Changing it only changes the report.',
    )

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res['mail_bounce_report_threshold'] = \
            self.env['mail.bounce.report']._bounce_threshold()
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        # Clamped to the range the report can actually apply: a value outside it
        # would be ignored by the view and the page would then display a
        # threshold nobody is using.
        threshold = min(max(int(self.mail_bounce_report_threshold or 0), 0),
                        MAX_THRESHOLD)
        # str() matters: set_param(0) would delete the parameter instead of
        # storing it, and the report would silently fall back to the default.
        self.env['ir.config_parameter'].sudo().set_param(
            PARAM_THRESHOLD, str(threshold))
