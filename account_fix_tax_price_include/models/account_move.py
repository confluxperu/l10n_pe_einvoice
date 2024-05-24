# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.osv import expression
from odoo.tools import float_compare, date_utils, email_split, email_re, float_is_zero
from odoo.tools.float_utils import float_round as round
from odoo.exceptions import UserError, ValidationError

import math
import logging
log = logging.getLogger(__name__)

TYPE_TAX_USE = [
    ('sale', 'Sales'),
    ('purchase', 'Purchases'),
    ('none', 'None'),
]

class AccountMove(models.Model):
    _inherit = "account.move"

    def _recompute_cash_rounding_lines(self):
        self.ensure_one()
        if self.move_type in ('out_invoice','out_refund') and self.company_id.fix_tax_price_include:
            self._recompute_tax_base_included_price_rounding_lines()
        super(AccountMove, self)._recompute_cash_rounding_lines()

    def _recompute_tax_base_included_price_rounding_lines(self):
        self.ensure_one()
        in_draft_mode = self != self._origin

        def _compute_tax_base_rounding(self, total_amount_currency):
            ''' Compute the amount differences due to the tax base rounding.
            :param self:                    The current account.move record.
            :param total_amount_currency:   The invoice's total in invoice's currency.
            :return:                        The amount differences both in company's currency & invoice's currency.
            '''

            lines_with_unrounded_amount = self.line_ids.filtered(lambda line: line.price_subtotal_unrounded>0 and (line.price_subtotal-line.price_total)!=0)
            price_grand_subtotal_rounded = abs(sum(lines_with_unrounded_amount.mapped('balance')))
            price_grand_subtotal_unrounded = sum(lines_with_unrounded_amount.mapped('price_subtotal_unrounded'))

            difference = self.company_id.currency_id.round(price_grand_subtotal_rounded-price_grand_subtotal_unrounded)
            if self.currency_id == self.company_id.currency_id:
                diff_amount_currency = diff_balance = difference
            else:
                diff_amount_currency = difference
                diff_balance = self.currency_id._convert(diff_amount_currency, self.company_id.currency_id, self.company_id, self.date)
            return diff_balance, diff_amount_currency
        
        def _apply_tax_base_rounding(self, diff_balance, diff_amount_currency, tax_base_rounding_line):
            rounding_line_vals = {
                'debit': diff_balance > 0.0 and diff_balance or 0.0,
                'credit': diff_balance < 0.0 and -diff_balance or 0.0,
                'quantity': 1.0,
                'amount_currency': diff_amount_currency,
                'partner_id': self.partner_id.id,
                'move_id': self.id,
                'currency_id': self.currency_id.id,
                'company_id': self.company_id.id,
                'company_currency_id': self.company_id.currency_id.id,
                'is_tax_base_rounding_line': True,
                #'exclude_from_invoice_tab': True,
                'sequence': 9999,
            }

            # add_invoice_line
            if diff_balance > 0.0 and self.journal_id.default_account_id:
                account_id = self.journal_id.default_account_id.id
            else:
                account_id = self.journal_id.default_account_id.id
            rounding_line_vals.update({
                'name': 'Rounding Tax Base',
                'account_id': account_id,
            })

            # Create or update the tax base rounding line.
            if tax_base_rounding_line:
                tax_base_rounding_line.update({
                    'amount_currency': rounding_line_vals['amount_currency'],
                    'debit': rounding_line_vals['debit'],
                    'credit': rounding_line_vals['credit'],
                    'account_id': rounding_line_vals['account_id'],
                })
            else:
                create_method = in_draft_mode and self.env['account.move.line'].new or self.env['account.move.line'].create
                tax_base_rounding_line = create_method(rounding_line_vals)

            if in_draft_mode:
                tax_base_rounding_line.update(tax_base_rounding_line._get_fields_onchange_balance(force_computation=True))

        #existing_cash_rounding_line
        existing_tax_base_rounding_line = self.line_ids.filtered(lambda line: line.is_tax_base_rounding_line)

        # The cash rounding has been removed.

        others_lines = self.line_ids.filtered(lambda line: line.account_id.user_type_id.type not in ('receivable', 'payable'))
        others_lines -= existing_tax_base_rounding_line
        total_amount_currency = sum(others_lines.mapped('amount_currency'))

        diff_balance, diff_amount_currency = _compute_tax_base_rounding(self, total_amount_currency)

        # The invoice is already rounded.
        if self.currency_id.is_zero(diff_balance) and self.currency_id.is_zero(diff_amount_currency):
            self.line_ids -= existing_tax_base_rounding_line
            return

        _apply_tax_base_rounding(self, diff_balance, diff_amount_currency, existing_tax_base_rounding_line)



class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    price_subtotal_unrounded = fields.Float(string='Price Subtotal Unrounded', default=0.0)
    is_tax_base_rounding_line = fields.Boolean(help="Technical field used to retrieve the tax base rounding line.")

    @api.model
    def _get_price_total_and_subtotal_model(self, price_unit, quantity, discount, currency, product, partner, taxes, move_type):
        ''' This method is used to compute 'price_total' & 'price_subtotal'.
        '''
        res = super(AccountMoveLine, self)._get_price_total_and_subtotal_model(price_unit, quantity, discount, currency, product, partner, taxes, move_type)
        price_subtotal_unrounded = 0
        if taxes:
            taxes_discount = taxes.compute_all(price_unit * (1 - (discount or 0.0) / 100.0), currency, quantity, product=product, partner=partner, is_refund=move_type in ('out_refund', 'in_refund'))  
            price_subtotal_unrounded = taxes_discount['total_excluded_unrounded']
        res['price_subtotal_unrounded'] = price_subtotal_unrounded
        return res