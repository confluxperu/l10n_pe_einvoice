# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import SUPERUSER_ID, api

def pre_init_hook(cr):
    '''env = api.Environment(cr, SUPERUSER_ID, {})
    pe_companies = env['res.company'].search([('partner_id.country_id.code', '=', 'PE')])
    pe_journals = env['account.journal'].search([('company_id', 'in', pe_companies.ids), ('type', '=', 'sale')])
    for pe_journal in pe_journals:
        if not env['account.move'].search([('posted_before', '=', True), ('journal_id', '=', pe_journal.id)], limit=1):
            pe_journal.l10n_latam_use_documents = True''
    '''
    cr.execute('''
        ALTER TABLE account_move
        ADD COLUMN l10n_pe_dte_amount_subtotal numeric,
        ADD COLUMN l10n_pe_dte_amount_discount numeric,
        ADD COLUMN l10n_pe_dte_amount_base numeric,
        ADD COLUMN l10n_pe_dte_amount_exonerated numeric,
        ADD COLUMN l10n_pe_dte_amount_free numeric,
        ADD COLUMN l10n_pe_dte_amount_unaffected numeric,
        ADD COLUMN l10n_pe_dte_amount_exportation numeric,
        ADD COLUMN l10n_pe_dte_amount_prepaid numeric,
        ADD COLUMN l10n_pe_dte_amount_untaxed numeric,
        ADD COLUMN l10n_pe_dte_global_discount numeric,
        ADD COLUMN l10n_pe_dte_amount_perception_base numeric,
        ADD COLUMN l10n_pe_dte_amount_perception_percentage numeric,
        ADD COLUMN l10n_pe_dte_amount_perception numeric,
        ADD COLUMN l10n_pe_dte_amount_icbper numeric,
        ADD COLUMN l10n_pe_dte_amount_igv numeric,
        ADD COLUMN l10n_pe_dte_amount_isc numeric,
        ADD COLUMN l10n_pe_dte_amount_others numeric,
        ADD COLUMN l10n_pe_dte_amount_total numeric,
        ADD COLUMN l10n_pe_dte_amount_total_with_perception numeric,
        ADD COLUMN invoice_payment_fee_total numeric
    ''')