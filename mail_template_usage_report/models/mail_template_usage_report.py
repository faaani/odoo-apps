# -*- coding: utf-8 -*-
# Part of mail_template_usage_report. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from odoo import fields, models, tools
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

# One template = one row. Every figure on the row comes from a grouped
# sub-select, so the whole report costs one query no matter how many templates
# the database holds - never a query per template.
BASE_QUERY = """
    SELECT t.id                                        AS id,
           t.id                                        AS template_id,
           t.model_id                                  AS model_id,
           t.model                                     AS model_name,
           t.lang                                      AS lang,
           COALESCE(t.auto_delete, FALSE)              AS auto_delete,
           {active_column}                             AS template_active,
           t.create_date                               AS template_create_date,
           t.write_date                                AS template_write_date,
           COALESCE(t.mtur_send_count, 0)              AS send_count,
           t.mtur_first_used                           AS first_used,
           GREATEST(t.mtur_last_used,
                    msg.last_date, ml.last_date)       AS last_used,
           COALESCE(msg.row_count, 0)                  AS message_count,
           COALESCE(ml.row_count, 0)                   AS mail_count,
           COALESCE(act.row_count, 0)                  AS server_action_count,
           {activity_count}                            AS activity_type_count,
           d.module                                    AS module,
           CASE WHEN d.module IS NULL
                THEN 'database' ELSE 'module' END      AS source,
           CASE
               -- created in this database: everything in it is custom
               WHEN d.module IS NULL THEN TRUE
               WHEN m.write_date IS NULL THEN FALSE
               -- edited after the module that ships it was last installed
               -- or upgraded
               WHEN t.write_date > m.write_date THEN TRUE
               ELSE FALSE
           END                                         AS customized
      FROM mail_template t
      LEFT JOIN (
              SELECT mail_template_id, COUNT(*) AS row_count, MAX(date) AS last_date
                FROM mail_message
               WHERE mail_template_id IS NOT NULL
            GROUP BY mail_template_id
           ) msg ON msg.mail_template_id = t.id
      LEFT JOIN (
              SELECT mail_template_id, COUNT(*) AS row_count, MAX(create_date) AS last_date
                FROM mail_mail
               WHERE mail_template_id IS NOT NULL
            GROUP BY mail_template_id
           ) ml ON ml.mail_template_id = t.id
      LEFT JOIN (
              SELECT template_id, COUNT(*) AS row_count
                FROM ir_act_server
               WHERE template_id IS NOT NULL
            GROUP BY template_id
           ) act ON act.template_id = t.id
      {activity_join}
      LEFT JOIN (
              SELECT res_id, MIN(module) AS module
                FROM ir_model_data
               WHERE model = 'mail.template'
                 AND LEFT(module, 2) <> '__'
            GROUP BY res_id
           ) d ON d.res_id = t.id
      LEFT JOIN ir_module_module m ON m.name = d.module
"""

REPORT_QUERY = """
    WITH base AS (
    {base}
    )
    SELECT b.*,
           (b.last_used IS NULL AND b.send_count = 0)          AS never_used,
           (b.server_action_count + b.activity_type_count)     AS reference_count,
           (b.server_action_count + b.activity_type_count > 0) AS referenced,
           (b.last_used IS NOT NULL OR b.send_count > 0
            OR b.server_action_count + b.activity_type_count > 0) AS in_use,
           CASE
               WHEN b.last_used IS NULL AND b.send_count = 0 THEN 'never'
               WHEN b.last_used >= (now() AT TIME ZONE 'UTC') - interval '90 days'
                    THEN 'recent'
               ELSE 'stale'
           END                                                 AS usage_status
      FROM base b
"""


class MailTemplateUsageReport(models.Model):
    _name = 'mail.template.usage.report'
    _description = 'Email Template Usage Report'
    _auto = False
    _rec_name = 'name'
    _order = 'send_count desc, id'

    template_id = fields.Many2one(
        'mail.template', string='Template', readonly=True,
        help='The email template this line reports on.')
    name = fields.Char(
        related='template_id.name', string='Template Name', readonly=True)
    subject = fields.Char(
        related='template_id.subject', string='Subject', readonly=True)
    model_id = fields.Many2one(
        'ir.model', string='Applies To', readonly=True,
        help='Model the template renders on.')
    model_name = fields.Char(string='Model', readonly=True)
    lang = fields.Char(
        string='Language', readonly=True,
        help='Language expression the template renders in. Empty means the '
             'recipient / record language is used.')
    template_active = fields.Boolean(
        string='Enabled', readonly=True,
        help='Unticked for archived templates.')
    auto_delete = fields.Boolean(
        string='Auto Delete', readonly=True,
        help='When ticked, Odoo deletes the email (and its chatter message) '
             'right after sending it. Such templates leave no stored mail '
             'behind, which is why this report keeps its own counter.')
    template_create_date = fields.Datetime(string='Created On', readonly=True)
    template_write_date = fields.Datetime(string='Last Modified On', readonly=True)

    send_count = fields.Integer(
        string='Emails Produced', readonly=True,
        help='Emails/messages produced from this template since this module '
             'was installed. Sends from before the installation cannot be '
             'counted: Odoo stores no link between an email and its template.')
    first_used = fields.Datetime(
        string='First Used', readonly=True,
        help='First send recorded here, i.e. when tracking started to see this '
             'template.')
    last_used = fields.Datetime(
        string='Last Used', readonly=True,
        help='Most recent evidence of use: the last recorded send, or the most '
             'recent mail/message still stored for this template.')
    message_count = fields.Integer(
        string='Messages Stored', readonly=True,
        help='Messages produced from this template that are still stored in '
             'the database (chatter history).')
    mail_count = fields.Integer(
        string='Emails Stored', readonly=True,
        help='Outgoing mails produced from this template that are still stored '
             '(queued, failed, or kept because Auto Delete is off).')

    server_action_count = fields.Integer(
        string='Server Actions', readonly=True,
        help='Server actions and automated actions configured to send this '
             'template.')
    activity_type_count = fields.Integer(
        string='Activity Types', readonly=True,
        help='Activity types offering this template when an activity is '
             'scheduled.')
    reference_count = fields.Integer(string='References', readonly=True)
    referenced = fields.Boolean(
        string='Referenced', readonly=True,
        help='Ticked when a server action, an automated action or an activity '
             'type points at this template.')

    never_used = fields.Boolean(
        string='Never Used', readonly=True,
        help='No send was recorded and no mail or message produced from this '
             'template is stored. This is NOT a permission to delete it: '
             'templates are also called from Python code and from settings of '
             'other apps, which this report cannot see.')
    in_use = fields.Boolean(
        string='In Use', readonly=True,
        help='Ticked when the template was used at least once, or when a '
             'server action / automated action / activity type points at it.')
    usage_status = fields.Selection(
        [('never', 'Never Used'),
         ('recent', 'Used in the Last 90 Days'),
         ('stale', 'Not Used in 90+ Days')],
        string='Usage', readonly=True)

    module = fields.Char(
        string='Module', readonly=True,
        help='Module that shipped this template. Empty when the template was '
             'created in this database.')
    source = fields.Selection(
        [('module', 'Shipped by a Module'),
         ('database', 'Created in this Database')],
        string='Source', readonly=True)
    customized = fields.Boolean(
        string='Customized', readonly=True,
        help='Ticked when the template was created in this database, or when '
             'it was modified after the module shipping it was last installed '
             'or upgraded. Upgrading that module re-applies its own version of '
             'the template, which clears this flag again.')

    # ------------------------------------------------------------------

    def _mtur_activity_type_sources(self):
        """Return the ``(count expression, join)`` for activity types offering
        a template.

        The many2many table is read from the live registry instead of being
        hard-coded, because its name is generated by Odoo and has moved
        between versions. When the relation is not usable the report reports 0
        rather than guessing.
        """
        field = self.env['mail.activity.type']._fields.get('mail_template_ids')
        if not field or field.type != 'many2many' or not field.store:
            return '0', ''
        relation = getattr(field, 'relation', None)
        column2 = getattr(field, 'column2', None)
        if not relation or not column2 or not table_exists(self.env.cr, relation):
            _logger.info(
                "mail_template_usage_report: activity-type references are not "
                "available on this database, reporting 0 for them.")
            return '0', ''
        join = (
            "LEFT JOIN (\n"
            "        SELECT %(column2)s AS template_id, COUNT(*) AS row_count\n"
            "          FROM %(relation)s\n"
            "      GROUP BY %(column2)s\n"
            "     ) att ON att.template_id = t.id"
        ) % {'column2': column2, 'relation': relation}
        return 'COALESCE(att.row_count, 0)', join

    def _mtur_view_sql(self):
        """Build the SELECT the report view is made of."""
        activity_count, activity_join = self._mtur_activity_type_sources()
        base = BASE_QUERY.format(
            # mail.template only gained `active` in 16.0.
            active_column='t.active' if 'active' in self.env['mail.template']._fields else 'TRUE',
            activity_count=activity_count,
            activity_join=activity_join,
        )
        return REPORT_QUERY.format(base=base)

    def init(self):
        # Read-only database view: this module never writes to mail.template
        # through the report. Everything interpolated below comes from the
        # running registry (the view name derived from _name, the mail.template
        # column layout and the auto-generated many2many table); no user input
        # reaches this SQL.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            'CREATE VIEW %s AS (%s)' % (self._table, self._mtur_view_sql()))

    def action_view_source_mails(self):
        """Open the emails still stored for this template."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Emails From This Template',
            'res_model': 'mail.mail',
            'view_mode': 'list,form',
            'domain': [('mail_template_id', '=', self.template_id.id)],
            'context': {'create': False},
        }

    def action_view_source_messages(self):
        """Open the chatter messages still stored for this template."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Messages From This Template',
            'res_model': 'mail.message',
            'view_mode': 'list,form',
            'domain': [('mail_template_id', '=', self.template_id.id)],
            'context': {'create': False},
        }
