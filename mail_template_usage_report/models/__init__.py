# -*- coding: utf-8 -*-
# mail_template is imported FIRST on purpose: Odoo runs _auto_init() and init()
# model by model, in registration order. The report below is an SQL view over
# the tracking columns added to mail_template, so those columns must exist by
# the time the view is created.
from . import mail_template
from . import mail_mail
from . import mail_message
from . import mail_compose_message
from . import mail_template_usage_report
