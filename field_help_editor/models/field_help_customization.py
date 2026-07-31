# -*- coding: utf-8 -*-
# Part of field_help_editor. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
from odoo import api, fields, models


class FieldHelpCustomization(models.Model):
    """One row per (field, language) whose label or tooltip was customized.

    The row keeps the values Odoo shipped (so "Reset" is exact) and the values
    currently applied (so a customization can be re-applied after a module
    upgrade has restored the built-in label).
    """
    _name = 'field.help.customization'
    _description = 'Field Label Customization'
    _rec_name = 'field_id'
    _order = 'model_name, field_name, lang'

    field_id = fields.Many2one(
        'ir.model.fields', string='Field', required=True, ondelete='cascade', index=True)
    lang = fields.Char(
        string='Language Code', required=True, index=True,
        help="Labels and tooltips are translatable: this entry only describes "
             "the values of this language.")
    lang_name = fields.Char(string='Language', compute='_compute_lang_name')
    model_name = fields.Char(
        related='field_id.model', string='Model', store=True, readonly=True)
    field_name = fields.Char(
        related='field_id.name', string='Technical Name', store=True, readonly=True)
    original_description = fields.Char(
        string='Original Label', required=True, readonly=True,
        help="Label this field had before it was customized for the first time.")
    original_help = fields.Text(
        string='Original Tooltip', readonly=True,
        help="Tooltip this field had before it was customized for the first time.")
    custom_description = fields.Char(
        string='Custom Label', readonly=True,
        help="Label currently applied by this customization.")
    custom_help = fields.Text(
        string='Custom Tooltip', readonly=True,
        help="Tooltip currently applied by this customization.")

    _field_lang_uniq = models.Constraint(
        'UNIQUE (field_id, lang)',
        'A field can only be customized once per language.',
    )

    def _compute_lang_name(self):
        names = {
            lang.code: lang.name
            for lang in self.env['res.lang'].with_context(active_test=False).search([])
        }
        for customization in self:
            customization.lang_name = names.get(customization.lang) or customization.lang

    def action_reset(self):
        """Put the original label and tooltip back and forget the entry."""
        fields_to_reset = self.mapped('field_id')
        # authorize before touching anything, not once the work is done
        fields_to_reset._fhe_check_customization_allowed()
        for customization in self:
            customization.field_id._fhe_restore_original(customization)
        self.unlink()
        fields_to_reset._fhe_clear_caches()
        return True

    def action_reapply(self):
        """Write the customized label and tooltip again.

        Useful after upgrading the module that owns the field: reflection then
        restores the label written in Python.
        """
        fields_to_apply = self.mapped('field_id')
        fields_to_apply._fhe_check_customization_allowed()
        for customization in self:
            customization.field_id._fhe_apply_values({
                'field_description': customization.custom_description,
                'help': customization.custom_help,
            }, customization.lang)
        fields_to_apply._fhe_clear_caches()
        return True

    @api.model
    def _fhe_for_fields(self, field_ids, lang):
        return self.search([('field_id', 'in', list(field_ids)), ('lang', '=', lang)])
