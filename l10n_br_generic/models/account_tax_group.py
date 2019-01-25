# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountTaxGroup(models.Model):
    _inherit = 'account.tax.group'

    domain = fields.Selection(
        selection=[('icms', 'ICMS'),
                   ('icmsst', 'ICMS ST'),
                   ('icmsfcp', 'ICMS FCP'),
                   ('icmsinter', 'ICMS Inter'),
                   ('ipi', 'IPI'),
                   ('cofins', 'COFINS'),
                   ('pis', 'PIS'),
                   ('issqn', 'ISSQN'),
                   ('irpf', 'IRPF'),
                   ('irpj', 'IRPJ'),
                   ('ii', 'II'),
                   ('csll', 'CSLL'),
                   ('other', 'Outra')],
        string='Tax Domain')

    tax_discount = fields.Boolean(
        string='Discount this Tax in Prince',
        help="Mark it for (ICMS, PIS e etc.).")
