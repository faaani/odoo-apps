# -*- coding: utf-8 -*-
# Part of field_help_editor. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
"""Let a tooltip stored on ``ir.model.fields`` win even when the Python field
defines no help at all.

Odoo already resolves a field *label* that way:
``Field._description_string()`` reads the label stored on ``ir.model.fields``
for the current language and falls back to the value written in Python.

``Field._description_help()`` does the very same thing, but only when the field
already has a help text in Python (``if self.help and env.lang``).  Most fields
have none, so a tooltip typed by an administrator would silently be ignored.

This patch drops that single condition, which makes the help behave exactly like
the label.  The value returned is still the one stored on ``ir.model.fields``,
which for every untouched field is what module reflection wrote there from the
Python source.

A worker process can serve several databases, and patching a class patches the
whole process, so the new behaviour is applied only to the databases where this
module is installed - detected by the presence of its model in the registry.
Everywhere else the original implementation is called, unchanged.
"""
from odoo import fields

_original_description_help = fields.Field._description_help


def _description_help(self, env):
    if env.lang and 'field.help.customization' in env:
        field_help = env['ir.translation'].get_field_help(self.base_field.model_name)
        return field_help.get(self.name) or self.help
    return _original_description_help(self, env)


fields.Field._description_help = _description_help
