# -*- coding: utf-8 -*-
from odoo import fields, models

class IrSequence(models.Model):

    _inherit = 'ir.sequence'

    l10n_pe_journal_ids = fields.Many2many('account.journal', 'l10n_pe_journal_sequence_rel', 'sequence_id', 'journal_id', 'Journals', readonly=True)