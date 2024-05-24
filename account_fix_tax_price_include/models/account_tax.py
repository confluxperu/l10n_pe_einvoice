# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.osv import expression
from odoo.tools import float_compare, date_utils, email_split, email_re, float_is_zero
from odoo.tools.float_utils import float_round as round
from odoo.exceptions import UserError, ValidationError

import math
import logging
log = logging.getLogger(__name__)

class AccountTax(models.Model):
    _inherit = "account.tax"
    
    def compute_all(self, price_unit, currency=None, quantity=1.0, product=None, partner=None, is_refund=False, handle_price_include=True):
        if not self:
            company = self.env.company
        else:
            company = self[0].company_id
        if company.fix_tax_price_include:
            taxes, groups_map = self.flatten_taxes_hierarchy(create_map=True)
            if not currency:
                currency = company.currency_id
            prec = currency.rounding

            round_tax = False
            if 'round' in self.env.context:
                round_tax = bool(self.env.context['round'])

            if not round_tax:
                prec *= 1e-5

            def recompute_base(base_amount, fixed_amount, percent_amount, division_amount):
                return (base_amount - fixed_amount) / (1.0 + percent_amount / 100.0) * (100 - division_amount) / 100

            #base = currency.round(price_unit * quantity)
            base = price_unit * quantity

            sign = 1
            if currency.is_zero(base):
                sign = self._context.get('force_sign', 1)
            elif base < 0:
                sign = -1
            if base < 0:
                base = -base

            # Store the totals to reach when using price_include taxes (only the last price included in row)
            total_included_checkpoints = {}
            i = len(taxes) - 1
            store_included_tax_total = True
            # Keep track of the accumulated included fixed/percent amount.
            incl_fixed_amount = incl_percent_amount = incl_division_amount = 0
            # Store the tax amounts we compute while searching for the total_excluded
            cached_tax_amounts = {}
            if handle_price_include:
                for tax in reversed(taxes):
                    tax_repartition_lines = (
                        is_refund
                        and tax.refund_repartition_line_ids
                        or tax.invoice_repartition_line_ids
                    ).filtered(lambda x: x.repartition_type == "tax")
                    sum_repartition_factor = sum(tax_repartition_lines.mapped("factor"))

                    if tax.include_base_amount:
                        base = recompute_base(base, incl_fixed_amount, incl_percent_amount, incl_division_amount)
                        incl_fixed_amount = incl_percent_amount = incl_division_amount = 0
                        store_included_tax_total = True
                    if tax.price_include or self._context.get('force_price_include'):
                        if tax.amount_type == 'percent':
                            incl_percent_amount += tax.amount * sum_repartition_factor
                        elif tax.amount_type == 'division':
                            incl_division_amount += tax.amount * sum_repartition_factor
                        elif tax.amount_type == 'fixed':
                            incl_fixed_amount += abs(quantity) * tax.amount * sum_repartition_factor
                        else:
                            # tax.amount_type == other (python)
                            tax_amount = tax._compute_amount(base, sign * price_unit, quantity, product, partner) * sum_repartition_factor
                            incl_fixed_amount += tax_amount
                            # Avoid unecessary re-computation
                            cached_tax_amounts[i] = tax_amount
                        # In case of a zero tax, do not store the base amount since the tax amount will
                        # be zero anyway. Group and Python taxes have an amount of zero, so do not take
                        # them into account.
                        if store_included_tax_total and (
                            tax.amount or tax.amount_type not in ("percent", "division", "fixed")
                        ):
                            total_included_checkpoints[i] = base
                            store_included_tax_total = False
                    i -= 1

            total_excluded_base = recompute_base(base, incl_fixed_amount, incl_percent_amount, incl_division_amount)
            #total_excluded = currency.round(total_excluded_base)
            total_excluded = round(total_excluded_base,10)

            # 4) Iterate the taxes in the sequence order to compute missing tax amounts.
            # Start the computation of accumulated amounts at the total_excluded value.
            base = total_included = total_void = total_excluded

            # Flag indicating the checkpoint used in price_include to avoid rounding issue must be skipped since the base
            # amount has changed because we are currently mixing price-included and price-excluded include_base_amount
            # taxes.
            skip_checkpoint = False

            taxes_vals = []
            i = 0
            cumulated_tax_included_amount = 0
            for tax in taxes:
                tax_repartition_lines = (is_refund and tax.refund_repartition_line_ids or tax.invoice_repartition_line_ids).filtered(lambda x: x.repartition_type == 'tax')
                sum_repartition_factor = sum(tax_repartition_lines.mapped('factor'))

                price_include = self._context.get('force_price_include', tax.price_include)

                #compute the tax_amount
                if not skip_checkpoint and price_include and total_included_checkpoints.get(i) is not None and sum_repartition_factor != 0:
                    # We know the total to reach for that tax, so we make a substraction to avoid any rounding issues
                    tax_amount = total_included_checkpoints[i] - (base + cumulated_tax_included_amount)
                    cumulated_tax_included_amount = 0
                else:
                    tax_amount = tax.with_context(force_price_include=False)._compute_amount(
                        base, sign * price_unit, quantity, product, partner)

                # Round the tax_amount multiplied by the computed repartition lines factor.
                tax_amount = round(tax_amount, precision_rounding=prec)
                factorized_tax_amount = round(tax_amount * sum_repartition_factor, precision_rounding=prec)

                if price_include and total_included_checkpoints.get(i) is None:
                    cumulated_tax_included_amount += factorized_tax_amount

                # If the tax affects the base of subsequent taxes, its tax move lines must
                # receive the base tags and tag_ids of these taxes, so that the tax report computes
                # the right total
                subsequent_taxes = self.env['account.tax']
                subsequent_tags = self.env['account.account.tag']
                if tax.include_base_amount:
                    subsequent_taxes = taxes[i+1:]
                    subsequent_tags = subsequent_taxes.get_tax_tags(is_refund, 'base')

                # Compute the tax line amounts by multiplying each factor with the tax amount.
                # Then, spread the tax rounding to ensure the consistency of each line independently with the factorized
                # amount. E.g:
                #
                # Suppose a tax having 4 x 50% repartition line applied on a tax amount of 0.03 with 2 decimal places.
                # The factorized_tax_amount will be 0.06 (200% x 0.03). However, each line taken independently will compute
                # 50% * 0.03 = 0.01 with rounding. It means there is 0.06 - 0.04 = 0.02 as total_rounding_error to dispatch
                # in lines as 2 x 0.01.
                repartition_line_amounts = [round(tax_amount * line.factor, precision_rounding=prec) for line in tax_repartition_lines]
                total_rounding_error = round(factorized_tax_amount - sum(repartition_line_amounts), precision_rounding=prec)
                nber_rounding_steps = int(abs(total_rounding_error / currency.rounding))
                rounding_error = round(nber_rounding_steps and total_rounding_error / nber_rounding_steps or 0.0, precision_rounding=prec)

                for repartition_line, line_amount in zip(tax_repartition_lines, repartition_line_amounts):

                    if nber_rounding_steps:
                        line_amount += rounding_error
                        nber_rounding_steps -= 1

                    taxes_vals.append({
                        'id': tax.id,
                        'name': partner and tax.with_context(lang=partner.lang).name or tax.name,
                        'amount': sign * line_amount,
                        'base': round(sign * base, precision_rounding=prec),
                        'sequence': tax.sequence,
                        'account_id': tax.cash_basis_transition_account_id.id if tax.tax_exigibility == 'on_payment' else repartition_line.account_id.id,
                        'analytic': tax.analytic,
                        'price_include': price_include,
                        'tax_exigibility': tax.tax_exigibility,
                        'tax_repartition_line_id': repartition_line.id,
                        'group': groups_map.get(tax),
                        'tag_ids': (repartition_line.tag_ids + subsequent_tags).ids,
                        'tax_ids': subsequent_taxes.ids,
                    })

                    if not repartition_line.account_id:
                        total_void += line_amount

                # Affect subsequent taxes
                if tax.include_base_amount:
                    base += factorized_tax_amount
                    if not price_include:
                        skip_checkpoint = True

                total_included += factorized_tax_amount
                i += 1

            return {
                'base_tags': taxes.mapped(is_refund and 'refund_repartition_line_ids' or 'invoice_repartition_line_ids').filtered(lambda x: x.repartition_type == 'base').mapped('tag_ids').ids,
                'taxes': taxes_vals,
                'total_excluded': sign * round(total_excluded,10),
                'total_included': sign * round(total_included,10),
                'total_void': sign * round(total_void,10),
                'total_excluded_unrounded': sign * round(total_excluded,10)
            }
        else:
            res = super(AccountTax, self).compute_all(price_unit, currency=currency, quantity=quantity, product=product, partner=partner, is_refund=is_refund, handle_price_include=handle_price_include)
            res['total_excluded_unrounded'] = res['total_excluded']
            return res