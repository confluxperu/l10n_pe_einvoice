# -*- coding: utf-8 -*-

from odoo import fields, models, api

class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_pe_sequence_ids = fields.Many2many(
        'ir.sequence', 'l10n_pe_journal_sequence_rel', 'journal_id', 'sequence_id', string='Sequences (pe)',
        domain="[('l10n_latam_document_type_id', '!=', False)]")